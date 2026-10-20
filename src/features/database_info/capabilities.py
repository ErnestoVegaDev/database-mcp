"""Static introspection queries and the pure version/feature logic (T6).

Everything in this module is pure: no MCP types, no SQLAlchemy, no sessions.
``get_database_info`` runs one of the two static statements below per engine
(one round trip), feeds the raw strings through :func:`parse_version` and the
feature matrix builders, and assembles the payload. Keeping the logic free of
I/O is what lets the self-check vectors run without a database.

The statements are server-authored, like the catalog queries of the sibling
slices: no caller input ever reaches their text, so the read-only guard does
not apply — there is no untrusted statement to guard.
"""

from __future__ import annotations

import re
from typing import TypedDict

# The seven reported capabilities, in the exact order the payload must carry
# them. This tuple is the contract: the matrices are built by iterating it, so
# the key order can never drift from what the tool documents.
FEATURE_KEYS: tuple[str, ...] = (
    "procedures",
    "cte",
    "recursive_cte",
    "window_functions",
    "json",
    "returning",
    "upsert",
)

# current_setting('server_version') is the bare version string ('16.4',
# '17beta1'); version() was rejected because it appends OS/architecture noise
# ('16.4 on x86_64-pc-linux-gnu ... compiled by ...'). server_version_num is
# a pure integer by PostgreSQL design (16.4 -> 160004, betas -> 170000), which
# makes it the gate source for the feature matrix — display-parse quirks can
# then never break gating. array_agg over an empty pg_extension yields NULL,
# which the slice maps to an empty list.
POSTGRES_INFO_SQL = """\
SELECT current_setting('server_version')     AS raw,
       current_setting('server_version_num') AS num,
       (SELECT array_agg(e.extname ORDER BY e.extname)
          FROM pg_catalog.pg_extension e)    AS extensions
"""

# MariaDB exposes its version only through VERSION(): there is no
# server_version_num equivalent, so the raw string is the single source for
# both display and gating. The alias keeps the column name identical to the
# PostgreSQL statement's first column, so both engines read ``row.raw``.
MARIA_INFO_SQL = "SELECT VERSION() AS raw"

# A leading dotted numeric run, exactly as the contract defines it:
# '16.4' -> ['16', '4'], '17beta1' -> ['17'], 'unknown' -> no match.
_LEADING_VERSION = re.compile(r"^\d+(?:\.\d+)*")


class ParsedVersion(TypedDict):
    """The display version: the raw server string plus its numeric parts.

    Attributes:
        raw: The version string exactly as the server reported it. For
            MariaDB the slice passes the original string here even when
            parsing ran on the shim-stripped form, so the payload echoes the
            server verbatim.
        major: Leading numeric component, or None when the string does not
            start with a number at all.
        minor: Second component, or None for a one-part version such as
            ``17beta1`` (major 17 only).
        patch: Third component, or None for one- and two-part versions.
    """

    raw: str
    major: int | None
    minor: int | None
    patch: int | None


def strip_maria_shim(raw: str) -> str:
    """Strip MariaDB's leading ``5.5.5-`` replication-compatibility prefix.

    MariaDB sometimes prefixes VERSION() with ``5.5.5-`` so ancient
    replication clients keep recognizing the server as "MySQL-like", e.g.
    ``5.5.5-10.6.12-MariaDB``. Parsing must start at ``10.6.12`` instead.
    The prefix is only removed when the remainder actually looks like a real
    MariaDB version (``N.N.N...-MariaDB``): genuine MariaDB 5.5 is EOL and
    out of scope, so a remainder that does not match is left untouched rather
    than misread as a modern release.

    Args:
        raw: The version string exactly as reported by the server.

    Returns:
        The string to parse: the remainder after the prefix when the prefix
        is a shim, otherwise ``raw`` unchanged.
    """
    if not raw.startswith("5.5.5-"):
        return raw
    remainder = raw[len("5.5.5-"):]
    if re.match(r"^\d+(?:\.\d+)+[^\s]*-MariaDB", remainder):
        return remainder
    return raw


def parse_version(source: str, raw: str | None = None) -> ParsedVersion:
    """Parse the leading dotted numeric parts of a version string.

    One part (``17beta1``) yields ``major`` only; two parts (``16.4``) yield
    ``major`` and ``minor``; three parts (``9.6.23``) fill all three. A
    string with no leading number at all parses to every part None — the
    caller treats that as "version unknown", never as a guess.

    Args:
        source: The string to parse. For MariaDB this is the output of
            :func:`strip_maria_shim`, not the raw server string.
        raw: The string to report as ``version.raw``. Defaults to
            ``source``; the slice passes the original server string so the
            payload echoes it verbatim even when parsing used another form.

    Returns:
        The parsed version with ``raw`` first, then ``major``, ``minor``,
        ``patch`` — the payload's key order.
    """
    reported = source if raw is None else raw
    match = _LEADING_VERSION.match(source)
    if match is None:
        return {"raw": reported, "major": None, "minor": None, "patch": None}

    parts = match.group(0).split(".")
    major = int(parts[0])
    minor = int(parts[1]) if len(parts) > 1 else None
    patch = int(parts[2]) if len(parts) > 2 else None
    return {"raw": reported, "major": major, "minor": minor, "patch": patch}


def null_features() -> dict[str, bool | None]:
    """Return the full feature matrix with every capability unknown.

    Used whenever a version could not be determined: an unknown capability
    must surface as ``null``, never as a guessed ``false``.
    """
    return dict.fromkeys(FEATURE_KEYS, None)


def _coerce_int(value: object) -> int | None:
    """Return ``value`` as an int, or None when it is not one.

    ``server_version_num`` arrives as text from PostgreSQL; converting in one
    place keeps a malformed value from raising — an unusable gate source must
    degrade to "unknown", not to an exception.
    """
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# PostgreSQL feature gates on server_version_num. Each value is the
# version_num of the release that introduced the capability: 80200 = 8.2,
# 80400 = 8.4, 090100 = 9.1, 090400 = 9.4, 090500 = 9.5, 110000 = 11.0.
# Keyed in FEATURE_KEYS order; the builder iterates FEATURE_KEYS so the
# payload order is the contract's, and a missing gate fails loudly.
_POSTGRES_GATES: dict[str, int] = {
    "procedures": 110000,
    "cte": 90100,
    "recursive_cte": 90100,
    "window_functions": 80400,
    "json": 90400,
    "returning": 80200,
    "upsert": 90500,
}

# MariaDB gained CTEs, recursive CTEs, window functions, and JSON in 10.2.
_MARIA_CAPABILITY_FLOOR: tuple[int, int] = (10, 2)


def build_postgres_features(
    version: ParsedVersion, version_num: object
) -> dict[str, bool | None]:
    """Return the PostgreSQL feature matrix for a reported version.

    Args:
        version: The parsed display version. When its major part is missing
            the string was not a version at all, so every capability is
            unknown — a report from an unreadable server cannot gate
            anything.
        version_num: The raw ``server_version_num`` value as returned by the
            driver (normally text such as ``"160004"``). This — not the
            display string — is the gate source, so suffix quirks like
            ``17beta1`` never break gating. None or a non-integer value
            leaves every capability unknown.

    Returns:
        The matrix keyed by ``FEATURE_KEYS`` in order: booleans when the
        version was readable, ``None`` (JSON ``null``) when it was not —
        never a guessed ``false``.
    """
    if version["major"] is None:
        return null_features()
    num = _coerce_int(version_num)
    if num is None:
        return null_features()
    return {key: num >= _POSTGRES_GATES[key] for key in FEATURE_KEYS}


def build_maria_features(version: ParsedVersion) -> dict[str, bool | None]:
    """Return the MariaDB feature matrix for a reported version.

    Gating runs on the parsed ``(major, minor)`` pair, because MariaDB's raw
    string is the single source of truth: a string that yields no usable pair
    leaves every capability unknown.

    ``returning`` is deliberately always False: MariaDB only added
    ``INSERT ... RETURNING`` in 10.5 and only for single-table INSERTs, and
    the approved contract reports it as unsupported so the model never writes
    a query that works on some servers and not others. ``procedures`` and
    ``upsert`` are always True once the version is readable — both features
    predate every MariaDB release this server supports.

    Args:
        version: The parsed display version (post shim-strip).

    Returns:
        The matrix keyed by ``FEATURE_KEYS`` in order, booleans or ``None``
        for an unreadable version.
    """
    major = version["major"]
    minor = version["minor"]
    if major is None or minor is None:
        return null_features()

    supported = (major, minor) >= _MARIA_CAPABILITY_FLOOR
    return {
        "procedures": True,
        "cte": supported,
        "recursive_cte": supported,
        "window_functions": supported,
        "json": supported,
        "returning": False,
        "upsert": True,
    }
