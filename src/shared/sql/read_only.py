"""Lexical read-only guard for model-written SQL (decision D3).

This is the only thing that stands between a statement the model authored and
the database driver, so it is deliberately hand-rolled instead of regex-based:
a naive regex over the raw string can be fooled by a forbidden keyword hidden
inside a string literal, a quoted identifier, or a comment. The tokenizer
below walks the statement once and SKIPS those regions entirely, so only real
statement-body tokens are ever classified.

What the tokenizer skips (never classifies):

* string literals ``'...'`` with the ``''`` escape;
* quoted identifiers ``"..."`` (PostgreSQL) and ``` `...` ``` (MariaDB),
  also with a doubled-quote escape — skipped as identifiers, not words;
* line comments ``-- ...`` and block comments ``/* ... */``. Block comments
  do NOT nest (matching PostgreSQL's rule; MariaDB nests them, so a nested
  MariaDB comment is treated as ending at its first ``*/`` — anything after
  that is tokenized normally, which can only make the guard stricter, never
  more permissive).

Classification rules, in order:

1. Tokenize the statement into word tokens (uppercased) and ``;`` tokens.
2. At most ONE ``;``, and it must be the FINAL meaningful token. Anything
   else is a multi-statement rejection. An empty / whitespace-only /
   comment-only statement is a rejection too.
3. The first body token must be in the allowlist ``SELECT``, ``SHOW``,
   ``WITH``. Anything else (``EXPLAIN``, ``PRAGMA``, ``VALUES``, ...) is
   rejected by name.
4. Every body token is scanned against the forbidden-keyword list, because
   PostgreSQL allows data-modifying CTEs (``WITH d AS (DELETE FROM t
   RETURNING *) SELECT *``) — a read-only STARTER can still carry a write
   further in, so the allowlist alone is not enough.

KNOWN LIMITATION: this is LEXICAL classification. It cannot see side effects
inside function calls (``pg_terminate_backend``, ``pg_sleep``, nextval, ...).
The defense in depth is the server-side read-only transaction that
``execute_query`` opens before running the statement — that is a semantic
backstop this module does not replace.

API: values, not exceptions (decision D5). :func:`ensure_read_only` returns
``None`` when the statement passes, otherwise a :class:`ValidationError`
whose message names the reason and the offending keyword only — never the
whole statement, never a connection string.
"""

from __future__ import annotations

from shared.domain.errors import ValidationError

# First-token allowlist: the statement must START with one of these.
_ALLOWED_STARTERS = frozenset({"SELECT", "SHOW", "WITH"})

# Forbidden anywhere in the body. Covers DML, DDL, transaction control,
# administration, and MySQL/MariaDB extras (INTO OUTFILE lands on INTO).
_FORBIDDEN_KEYWORDS = frozenset(
    {
        "INSERT",
        "UPDATE",
        "DELETE",
        "MERGE",
        "REPLACE",
        "CREATE",
        "ALTER",
        "DROP",
        "TRUNCATE",
        "RENAME",
        "GRANT",
        "REVOKE",
        "BEGIN",
        "COMMIT",
        "ROLLBACK",
        "SAVEPOINT",
        "RELEASE",
        "SET",
        "RESET",
        "CALL",
        "DO",
        "EXECUTE",
        "EXEC",
        "PREPARE",
        "DEALLOCATE",
        "COPY",
        "INTO",
        "LOCK",
        "UNLOCK",
        "VACUUM",
        "ANALYZE",
        "OPTIMIZE",
        "REPAIR",
        "FLUSH",
        "KILL",
        "SHUTDOWN",
        "USE",
        "LOAD",
        "INSTALL",
        "UNINSTALL",
        "COMMENT",
        "CLUSTER",
        "REINDEX",
        "REFRESH",
        "LISTEN",
        "NOTIFY",
        "DISCARD",
        "CHECKPOINT",
    }
)


def _skip_quoted(sql: str, start: int, quote: str) -> int:
    """Return the index just past the quoted region opened at ``start``.

    The closing quote is escaped by doubling (``''``, ``""``, ``` `` ```),
    the standard escape in both PostgreSQL and MariaDB. An unterminated
    quote swallows the rest of the input: the database would reject that
    statement anyway, and skipping keeps the guard fail-closed on the tokens
    that DID parse.
    """
    index = start + 1
    length = len(sql)
    while index < length:
        char = sql[index]
        if char != quote:
            index += 1
        elif index + 1 < length and sql[index + 1] == quote:
            # Doubled quote: an escaped quote inside the region, keep going.
            index += 2
        else:
            return index + 1
    return length


def _tokenize(sql: str) -> list[str]:
    """Split ``sql`` into uppercased word tokens and ``;`` tokens.

    Everything else — whitespace, string literals, quoted identifiers,
    comments, numbers, operators, punctuation — is skipped: it carries no
    keyword meaning for classification. The token list is therefore exactly
    the set of positions a forbidden keyword could hide in.
    """
    tokens: list[str] = []
    index = 0
    length = len(sql)
    while index < length:
        char = sql[index]
        if char.isspace():
            index += 1
        elif sql.startswith("--", index):
            # Line comment: skip to the end of the line (or end of input).
            newline = sql.find("\n", index)
            index = length if newline == -1 else newline + 1
        elif sql.startswith("/*", index):
            # Block comment: no nesting (documented above). An unterminated
            # block comment swallows the rest of the input, same fail-closed
            # reasoning as an unterminated quote.
            end = sql.find("*/", index + 2)
            index = length if end == -1 else end + 2
        elif char == "'":
            index = _skip_quoted(sql, index, "'")
        elif char == '"':
            index = _skip_quoted(sql, index, '"')
        elif char == "`":
            index = _skip_quoted(sql, index, "`")
        elif char == ";":
            tokens.append(";")
            index += 1
        elif char.isalpha() or char == "_":
            start = index
            index += 1
            while index < length and (
                sql[index].isalnum() or sql[index] in "_$"
            ):
                index += 1
            # Uppercase once here so every comparison below is against the
            # canonical keyword spelling; SQL keywords are case-insensitive.
            tokens.append(sql[start:index].upper())
        else:
            # Numbers, operators, punctuation: no keyword meaning, skip.
            index += 1
    return tokens


def ensure_read_only(sql: str) -> ValidationError | None:
    """Return ``None`` when ``sql`` is a read-only statement, else the error.

    The error message names the REASON and the offending keyword only. It
    never echoes the statement back (it may contain data) and never touches
    a connection string.

    Args:
        sql: The raw statement the model wants to execute.

    Returns:
        ``None`` when the statement passes every rule; otherwise a
        :class:`~shared.domain.errors.ValidationError` describing the first
        rule that broke (empty statement, multi-statement, non-allowlisted
        starter, or a forbidden keyword).
    """
    tokens = _tokenize(sql)

    if not tokens:
        return ValidationError(
            "Empty statement; only SELECT, SHOW, or WITH statements are "
            "allowed.",
            field="sql",
        )

    # Semicolon rule: zero or one ';', and it must be the final meaningful
    # token. Only whitespace and comments may follow it — the tokenizer
    # already dropped those, so "final" means the last element of `tokens`.
    semicolon_count = tokens.count(";")
    if semicolon_count > 1:
        return ValidationError(
            "Multiple statements are not allowed; the statement contains "
            "more than one ';'.",
            field="sql",
        )
    if semicolon_count == 1 and tokens[-1] != ";":
        return ValidationError(
            "Multiple statements are not allowed; a ';' must be the final "
            "token of the statement.",
            field="sql",
        )

    # Body = every token except the optional trailing ';'. A lone ';' left
    # an empty body, which is rejected by the same rule as an empty input.
    body = [token for token in tokens if token != ";"]
    if not body:
        return ValidationError(
            "Empty statement; only SELECT, SHOW, or WITH statements are "
            "allowed.",
            field="sql",
        )

    # Allowlist on the first token. Quoted identifiers and literals were
    # skipped by the tokenizer, so a statement like `"update" FROM t` shows
    # FROM first and is rejected here — a quoted thing cannot vouch for the
    # statement's intent.
    first = body[0]
    if first not in _ALLOWED_STARTERS:
        allowed = ", ".join(sorted(_ALLOWED_STARTERS))
        return ValidationError(
            f"Statement must start with one of: {allowed}; "
            f"found {first!r} instead.",
            field="sql",
        )

    # Forbidden-token scan over ALL body tokens: a read-only WITH starter can
    # still carry a data-modifying CTE (PostgreSQL), and MySQL's
    # SELECT ... INTO OUTFILE hides its payload keyword mid-statement.
    for token in body:
        if token in _FORBIDDEN_KEYWORDS:
            return ValidationError(
                f"Keyword {token!r} is not allowed in a read-only statement.",
                field="sql",
            )

    return None
