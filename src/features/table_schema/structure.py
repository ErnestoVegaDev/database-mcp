"""Pure structure queries and payload folding for describe_tables.

Everything in this module is pure: no MCP types, no SQLAlchemy engines or
sessions. The per-engine statements below are server-authored, like the
catalog queries of the sibling slices: no caller input ever reaches their
text — ``:schema`` and the expanding ``:names`` are bind params, not
interpolations — so the read-only guard does not apply: there is no
untrusted statement to guard.

The fold turns fetched rows into the payload's ``tables`` and ``missing``
parts. It reads rows by attribute (``getattr``), which both SQLAlchemy
``Row`` objects and the plain stand-ins used by the self-check vectors
satisfy — that is what lets the folding vectors run without a database.

Ordering is split on purpose: the statements impose a stable order
(columns by ``ordinal_position``, foreign keys by constraint name then
column ordinal) and the fold preserves it while re-ordering tables to the
requested order — the repo rule against unstable ordering exists because
an unordered listing makes both paging and diffing lie.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from shared.persistence import SupportedEngine


@dataclass(frozen=True, slots=True)
class StructureQueries:
    """The three static statements one request runs, in execution order.

    Attributes:
        scope_sql: Resolves the scope actually in effect (the caller's
            ``schema`` or the engine's default) so the payload can echo
            it. Always binds ``:schema``.
        columns_sql: Column rows for the requested names, ordered by
            table then ordinal position. Binds ``:schema`` and the
            expanding ``:names``.
        constraints_sql: Primary-key and foreign-key rows for the
            requested names, ordered by table, constraint name, then
            column ordinal. Binds ``:schema`` and the expanding
            ``:names``.
    """

    scope_sql: str
    columns_sql: str
    constraints_sql: str


# Scope resolution is one tiny extra round trip: a SELECT without FROM
# echoes COALESCE(:schema, <engine default>) so the payload reports the
# scope actually used, never the raw null input. Folding it into the
# columns query instead would lose the scope whenever every requested name
# is missing (zero rows), which is exactly when the echo still matters.
_POSTGRES_SCOPE_SQL = """\
SELECT COALESCE(:schema, current_schema()) AS used_scope
"""

_MARIA_SCOPE_SQL = """\
SELECT COALESCE(:schema, DATABASE()) AS used_scope
"""

# PostgreSQL additionally excludes the system schemas: the default scope
# (current_schema()) cannot reach them anyway, but a caller-supplied
# 'information_schema' must not dump system tables. MariaDB naturally
# scopes to one database, so no extra exclusion is needed there.
_POSTGRES_COLUMNS_SQL = """\
SELECT c.table_name,
       c.column_name,
       c.ordinal_position,
       c.data_type,
       c.character_maximum_length,
       c.numeric_precision,
       c.numeric_scale,
       c.is_nullable,
       c.column_default
FROM information_schema.columns AS c
WHERE c.table_schema = COALESCE(:schema, current_schema())
  AND c.table_schema NOT IN ('pg_catalog', 'information_schema')
  AND c.table_name IN :names
ORDER BY c.table_name, c.ordinal_position
"""

_MARIA_COLUMNS_SQL = """\
SELECT c.table_name,
       c.column_name,
       c.ordinal_position,
       c.data_type,
       c.character_maximum_length,
       c.numeric_precision,
       c.numeric_scale,
       c.is_nullable,
       c.column_default
FROM information_schema.columns AS c
WHERE c.table_schema = COALESCE(:schema, DATABASE())
  AND c.table_name IN :names
ORDER BY c.table_name, c.ordinal_position
"""

# Foreign keys pair positionally through the referenced unique constraint:
# kcu.position_in_unique_constraint (where this FK column sits in the
# referenced constraint) joins kcu2.ordinal_position (where that referenced
# column sits), so a composite FK yields columns[i] <-> referenced_columns[i]
# without any per-row guesswork. The LEFT JOINs keep plain primary-key rows
# flowing with NULL referenced_* columns. Labels are aliased because kcu and
# kcu2 are the same view twice: two columns called table_name would collide
# on attribute access.
_CONSTRAINTS_BODY = """\
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
  ON kcu.constraint_schema = tc.constraint_schema
 AND kcu.constraint_name = tc.constraint_name
 AND kcu.table_schema = tc.table_schema
 AND kcu.table_name = tc.table_name
LEFT JOIN information_schema.referential_constraints AS rc
  ON rc.constraint_schema = tc.constraint_schema
 AND rc.constraint_name = tc.constraint_name
LEFT JOIN information_schema.key_column_usage AS kcu2
  ON kcu2.constraint_schema = rc.unique_constraint_schema
 AND kcu2.constraint_name = rc.unique_constraint_name
 AND kcu2.ordinal_position = kcu.position_in_unique_constraint
"""

_POSTGRES_CONSTRAINTS_SQL = """\
SELECT tc.table_name,
       tc.constraint_name,
       tc.constraint_type,
       kcu.column_name,
       kcu.ordinal_position,
       kcu.position_in_unique_constraint,
       kcu2.table_name AS referenced_table,
       kcu2.column_name AS referenced_column
""" + _CONSTRAINTS_BODY + """\
WHERE tc.constraint_type IN ('PRIMARY KEY', 'FOREIGN KEY')
  AND tc.table_schema = COALESCE(:schema, current_schema())
  AND tc.table_schema NOT IN ('pg_catalog', 'information_schema')
  AND tc.table_name IN :names
ORDER BY tc.table_name, tc.constraint_name, kcu.ordinal_position
"""

_MARIA_CONSTRAINTS_SQL = """\
SELECT tc.table_name,
       tc.constraint_name,
       tc.constraint_type,
       kcu.column_name,
       kcu.ordinal_position,
       kcu.position_in_unique_constraint,
       kcu2.table_name AS referenced_table,
       kcu2.column_name AS referenced_column
""" + _CONSTRAINTS_BODY + """\
WHERE tc.constraint_type IN ('PRIMARY KEY', 'FOREIGN KEY')
  AND tc.table_schema = COALESCE(:schema, DATABASE())
  AND tc.table_name IN :names
ORDER BY tc.table_name, tc.constraint_name, kcu.ordinal_position
"""

# Types whose declared length reads back as a real type modifier
# (character varying(50), varchar(50), binary(10)). Gated by name because
# MariaDB also reports a maximum length for the text family (text ->
# 65535, longtext -> 4294967295), which is a limit, not a modifier a
# caller could write in DDL.
_LENGTH_SUFFIX_TYPES = frozenset(
    {
        "character varying",
        "character",
        "bit varying",
        "bit",
        "varchar",
        "char",
        "nvarchar",
        "nchar",
        "varbinary",
        "binary",
    }
)

# The only family whose precision/scale pair is a declared modifier
# (numeric(12,2); MariaDB spells it decimal). Gated by name because the
# raw fields lie elsewhere: PostgreSQL reports numeric_precision=32 and
# numeric_scale=0 for a plain integer, and 24/53 for real/double
# precision — a mechanical "append whenever non-null" would emit
# integer(32,0) and real(24), neither of which is a declared modifier.
_DECIMAL_SUFFIX_TYPES = frozenset({"numeric", "decimal"})


def structure_queries(engine: SupportedEngine) -> StructureQueries:
    """Return the three static statements for ``engine``.

    Args:
        engine: The already-validated engine to describe tables of.

    Returns:
        The engine's statements in execution order: scope, columns,
        constraints. All three scope with COALESCE(:schema, <default>),
        so ``:schema`` is always bound (None meaning the engine's
        current default).

    Raises:
        ValueError: If the engine has no statements defined — a new
            enum member must bring its queries along, and failing loudly
            beats silently answering with another engine's data.
    """
    if engine is SupportedEngine.POSTGRES:
        return StructureQueries(
            scope_sql=_POSTGRES_SCOPE_SQL,
            columns_sql=_POSTGRES_COLUMNS_SQL,
            constraints_sql=_POSTGRES_CONSTRAINTS_SQL,
        )

    if engine is SupportedEngine.MARIA:
        return StructureQueries(
            scope_sql=_MARIA_SCOPE_SQL,
            columns_sql=_MARIA_COLUMNS_SQL,
            constraints_sql=_MARIA_CONSTRAINTS_SQL,
        )

    raise ValueError(
        f"No structure queries defined for engine {engine.value!r}."
    )


def compose_column_type(
    data_type: object,
    character_maximum_length: object,
    numeric_precision: object,
    numeric_scale: object,
) -> str:
    """Compose a readable column type from information_schema fields.

    The result reads like a declared type modifier:
    ``character varying(50)``, ``character(10)``, ``numeric(12,2)``, and
    the bare ``data_type`` otherwise (``integer``, ``text``, ...). Each
    suffix family is gated by type name because the raw fields are not
    trustworthy on their own — see ``_LENGTH_SUFFIX_TYPES`` and
    ``_DECIMAL_SUFFIX_TYPES`` above for the exact lies each gate blocks.

    Args:
        data_type: The ``information_schema.columns.data_type`` value,
            for example ``"character varying"`` or ``"integer"``.
        character_maximum_length: Declared length for character and bit
            string types, else None.
        numeric_precision: Reported precision (for PostgreSQL this is
            non-NULL for integer types too), else None.
        numeric_scale: Reported scale, else None.

    Returns:
        The composed type string, JSON-safe.
    """
    name = str(data_type)
    if name in _LENGTH_SUFFIX_TYPES and character_maximum_length is not None:
        return f"{name}({character_maximum_length})"
    if (
        name in _DECIMAL_SUFFIX_TYPES
        and numeric_precision is not None
        and numeric_scale is not None
    ):
        return f"{name}({numeric_precision},{numeric_scale})"
    return name


def fold_tables(
    requested: Sequence[str],
    column_rows: Iterable[Any],
    constraint_rows: Iterable[Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Fold fetched rows into the payload's ``tables`` and ``missing``.

    Row order is load-bearing and comes from the statements' ORDER BY:
    columns arrive by ordinal position (preserved as the column order)
    and constraints by table, constraint name, then column ordinal
    (preserved as the foreign-key order, first sight of a constraint
    starting a new entry).

    Args:
        requested: The de-duplicated requested names, in request order.
            Presence in the payload is an exact-name match against the
            rows' ``table_name`` — no case folding.
        column_rows: Column rows carrying ``table_name``,
            ``column_name``, ``data_type``,
            ``character_maximum_length``, ``numeric_precision``,
            ``numeric_scale``, ``is_nullable``, ``column_default``.
        constraint_rows: Primary-key/foreign-key rows carrying
            ``table_name``, ``constraint_name``, ``constraint_type``,
            ``column_name``, ``referenced_table``,
            ``referenced_column``.

    Returns:
        ``(tables, missing)``: every requested name that resolved, in
        request order, and every requested name that found no columns,
        in request order (``[]`` when none).
    """
    columns_by_table: dict[str, list[dict[str, Any]]] = {}
    for row in column_rows:
        table_name = str(getattr(row, "table_name"))
        column_default = getattr(row, "column_default")
        columns_by_table.setdefault(table_name, []).append(
            {
                "name": str(getattr(row, "column_name")),
                "type": compose_column_type(
                    getattr(row, "data_type"),
                    getattr(row, "character_maximum_length"),
                    getattr(row, "numeric_precision"),
                    getattr(row, "numeric_scale"),
                ),
                "nullable": str(getattr(row, "is_nullable")).upper()
                == "YES",
                "default": (
                    None if column_default is None else str(column_default)
                ),
                # Filled from the primary-key constraint rows below.
                "primary_key": False,
            }
        )

    foreign_keys_by_table: dict[str, dict[str, dict[str, Any]]] = {}
    for row in constraint_rows:
        table_name = str(getattr(row, "table_name"))
        columns = columns_by_table.get(table_name)
        if columns is None:
            # A constraint for a table the columns query did not return
            # (a drop between the two statements, or a case-variant name
            # outside exact matching): skip it rather than report a table
            # this payload cannot describe.
            continue
        constraint_type = str(getattr(row, "constraint_type"))
        if constraint_type == "PRIMARY KEY":
            by_name = {column["name"]: column for column in columns}
            column = by_name.get(str(getattr(row, "column_name")))
            if column is not None:
                column["primary_key"] = True
        elif constraint_type == "FOREIGN KEY":
            # Rows arrive ordered by constraint name then column ordinal,
            # so first sight of a constraint starts its entry and each
            # row appends the next (column, referenced_column) pair.
            per_table = foreign_keys_by_table.setdefault(table_name, {})
            name = str(getattr(row, "constraint_name"))
            entry = per_table.get(name)
            if entry is None:
                referenced_table = getattr(row, "referenced_table")
                entry = {
                    "name": name,
                    "columns": [],
                    "referenced_table": (
                        None
                        if referenced_table is None
                        else str(referenced_table)
                    ),
                    "referenced_columns": [],
                }
                per_table[name] = entry
            entry["columns"].append(str(getattr(row, "column_name")))
            referenced_column = getattr(row, "referenced_column")
            entry["referenced_columns"].append(
                None if referenced_column is None
                else str(referenced_column)
            )
        # Any other constraint type cannot appear (the statement filters
        # to PRIMARY KEY and FOREIGN KEY); skipping beats guessing.

    tables: list[dict[str, Any]] = []
    missing: list[str] = []
    for name in requested:
        columns = columns_by_table.get(name)
        if columns is None:
            missing.append(name)
            continue
        per_table = foreign_keys_by_table.get(name)
        tables.append(
            {
                "name": name,
                "columns": columns,
                "foreign_keys": (
                    [] if per_table is None else list(per_table.values())
                ),
            }
        )
    return tables, missing
