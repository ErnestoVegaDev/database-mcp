"""Server-authored catalog queries for schema discovery.

The statements in this module are how ``list_database_objects`` learns what an
engine contains. They are *not* model-authored SQL: the text is fixed here per
engine, the only bind param is ``:schema`` (bound through SQLAlchemy
``text()``), and no caller input is ever interpolated into a statement — which
is why the read-only guard (T4) does not apply to them.

Every query orders by ``schema, name``: the repo rule against unstable
ordering exists because an unordered listing makes both paging and diffing
lie.

Reporting is limited to four kinds — ``table``, ``view``, ``procedure``,
``function`` — because that is the vocabulary the model reasons in when it
writes its next SQL. A catalog type that does not map onto one of those four is
skipped, never guessed at: a mislabeled kind is worse than a missing row.
"""

from __future__ import annotations

from dataclasses import dataclass

from shared.persistence import SupportedEngine

# The complete vocabulary of reported kinds, in report order. It is both the
# allow-list for the tool's ``kinds`` filter and the zero-fill for ``counts``.
KINDS: tuple[str, ...] = ("table", "view", "procedure", "function")


@dataclass(frozen=True, slots=True)
class CatalogQuery:
    """One static catalog query and how its rows map onto reported kinds.

    Attributes:
        sql: The complete, engine-specific statement. Caller input never
            reaches this text; ``:schema`` is a bind param, not an
            interpolation.
        schema_column: Column holding the schema (PostgreSQL) or database
            (MariaDB) name.
        name_column: Column holding the object name.
        type_column: Column holding the catalog type of the object (for
            example ``BASE TABLE`` or ``VIEW``).
        kind_map: Catalog type value to reported kind. A type that is not a
            key here is skipped instead of guessed at.
        binds_schema: Whether the statement actually references ``:schema``.
            Only then may the executor bind it: referencing a param that was
            not bound, or binding one the statement does not use, are both
            execution errors.
    """

    sql: str
    schema_column: str
    name_column: str
    type_column: str
    kind_map: dict[str, str]
    binds_schema: bool


# PostgreSQL maps BASE TABLE and VIEW; every other table_type (FOREIGN TABLE,
# and whatever a future version adds) is deliberately left unmapped so it is
# skipped rather than reported under a kind it does not behave like.
_POSTGRES_RELATION_KINDS: dict[str, str] = {
    "BASE TABLE": "table",
    "VIEW": "view",
}

# PostgreSQL 11+ exposes procedures in information_schema.routines alongside
# functions, distinguishable by routine_type.
_POSTGRES_ROUTINE_KINDS: dict[str, str] = {
    "PROCEDURE": "procedure",
    "FUNCTION": "function",
}

# MariaDB reports BASE TABLE; the legacy spelling TABLE also occurs on older
# servers, and both mean a plain table.
_MARIA_RELATION_KINDS: dict[str, str] = {
    "BASE TABLE": "table",
    "TABLE": "table",
    "VIEW": "view",
}

_MARIA_ROUTINE_KINDS: dict[str, str] = {
    "PROCEDURE": "procedure",
    "FUNCTION": "function",
}

# {schema_clause} is filled with either a static AND fragment (schema given)
# or nothing (no schema). See catalog_queries for why PostgreSQL needs this
# while MariaDB does not.
_POSTGRES_TABLES_SQL = """\
SELECT table_schema, table_name, table_type
FROM information_schema.tables
WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
{schema_clause}\
ORDER BY table_schema, table_name
"""

_POSTGRES_ROUTINES_SQL = """\
SELECT routine_schema, routine_name, routine_type
FROM information_schema.routines
WHERE routine_schema NOT IN ('pg_catalog', 'information_schema')
{schema_clause}\
ORDER BY routine_schema, routine_name
"""

# MariaDB has no cheap "every schema" default we would want here: listing every
# database on the server would be noise and could leak names the caller was not
# pointed at, so the default scope is the CURRENT database (DATABASE()). A
# :schema naming a missing database simply matches nothing — an empty list is
# an expected outcome, not an error.
_MARIA_TABLES_SQL = """\
SELECT table_schema, table_name, table_type
FROM information_schema.tables
WHERE table_schema = COALESCE(:schema, DATABASE())
ORDER BY table_schema, table_name
"""

_MARIA_ROUTINES_SQL = """\
SELECT routine_schema, routine_name, routine_type
FROM information_schema.routines
WHERE routine_schema = COALESCE(:schema, DATABASE())
ORDER BY routine_schema, routine_name
"""


def catalog_queries(
    engine: SupportedEngine, schema: str | None
) -> tuple[CatalogQuery, ...]:
    """Return the catalog queries for ``engine``, scoped to ``schema``.

    Args:
        engine: The already-validated engine to list objects of.
        schema: One schema (PostgreSQL) or one database (MariaDB) to scope to,
            or None for the engine's default scope.

    Returns:
        The engine's queries in execution order: relations (tables and views)
        first, then routines (procedures and functions).

    Raises:
        ValueError: If the engine has no catalog queries defined — a new
            enum member must bring its queries along, and failing loudly beats
            silently answering with another engine's data.
    """
    if engine is SupportedEngine.POSTGRES:
        # PostgreSQL cannot COALESCE its way out of an unbound param the way
        # MariaDB can (``col = NULL`` is never true), so the schema filter is
        # a static fragment appended only when a schema was actually asked
        # for, and the param is bound only when the fragment is present.
        if schema is not None:
            tables_clause = "  AND table_schema = :schema\n"
            routines_clause = "  AND routine_schema = :schema\n"
        else:
            tables_clause = ""
            routines_clause = ""
        binds_schema = schema is not None
        return (
            CatalogQuery(
                sql=_POSTGRES_TABLES_SQL.format(schema_clause=tables_clause),
                schema_column="table_schema",
                name_column="table_name",
                type_column="table_type",
                kind_map=_POSTGRES_RELATION_KINDS,
                binds_schema=binds_schema,
            ),
            CatalogQuery(
                sql=_POSTGRES_ROUTINES_SQL.format(schema_clause=routines_clause),
                schema_column="routine_schema",
                name_column="routine_name",
                type_column="routine_type",
                kind_map=_POSTGRES_ROUTINE_KINDS,
                binds_schema=binds_schema,
            ),
        )

    if engine is SupportedEngine.MARIA:
        # COALESCE handles the unscoped case in SQL, so :schema is always
        # bound here (None meaning "current database").
        return (
            CatalogQuery(
                sql=_MARIA_TABLES_SQL,
                schema_column="table_schema",
                name_column="table_name",
                type_column="table_type",
                kind_map=_MARIA_RELATION_KINDS,
                binds_schema=True,
            ),
            CatalogQuery(
                sql=_MARIA_ROUTINES_SQL,
                schema_column="routine_schema",
                name_column="routine_name",
                type_column="routine_type",
                kind_map=_MARIA_ROUTINE_KINDS,
                binds_schema=True,
            ),
        )

    raise ValueError(f"No catalog queries defined for engine {engine.value!r}.")
