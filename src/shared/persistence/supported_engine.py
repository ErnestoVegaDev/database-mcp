"""Catalog of the database engines this server knows how to talk to.

An engine is "supported" when four facts line up:

* an environment variable that carries its async SQLAlchemy URL,
* the canonical URL scheme (driver) that variable should use,
* the plain schemes users are allowed to write instead, and
* a human-readable label for tool output.

Keeping those facts together in one place means the registry, the dispatcher,
and the tools all agree on the same vocabulary. A name or a scheme can no longer
be right in one place and wrong in another.

An engine has exactly one supported async driver, so a plain scheme (``postgres``,
``mysql``) is unambiguous: it names the engine, not the driver. The registry
therefore accepts those plain schemes as aliases and rewrites them to the single
canonical scheme before the URL reaches SQLAlchemy. An alias is *not* a driver
choice — there is only one driver to choose.

One engine can cover more than one vendor. MySQL and MariaDB share the driver,
the dialect, ``information_schema``, and the read-only transaction, so they are a
single member (``MARIA``) reached through two aliases, and the label names both.
That is not a merge of convenience: adding a second member for MySQL would make
``mysql://`` ambiguous between two engines and would report one database as two
different connections. A vendor that diverges in a way a slice can observe — a
different driver, dialect, catalog, or capability floor — is what earns its own
member.

The catalog uses ``StrEnum`` so a member compares and serializes as its plain
string value (``SupportedEngine.POSTGRES == "postgres"``). That makes it safe
to hand straight to JSON without a mapping table.

Adding a supported engine is exactly two edits: one enum member plus one entry
in the private spec map below. Env reading, scheme validation, and dispatch are
generic and pick the new engine up automatically.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


@dataclass(frozen=True, slots=True)
class _EngineSpec:
    """The static facts that make an engine "supported".

    Attributes:
        env_var: Environment variable holding the engine's async SQLAlchemy URL.
        url_schemes: URL schemes (drivers) this engine accepts, e.g.
            ``postgresql+asyncpg``. A URL for this engine must use one of them.
        alias_schemes: Plain, driver-less schemes users copy from a client or a
            DSN doc, e.g. ``postgresql``. Each is accepted and rewritten to the
            engine's single canonical scheme; an alias never selects a driver,
            because the engine has exactly one.
        label: Human-readable name for tool output and log messages. It names
            every server this engine reaches, not one vendor: the ``mysql``
            driver and dialect serve MySQL and MariaDB alike, so the label
            says both.
    """

    env_var: str
    url_schemes: tuple[str, ...]
    alias_schemes: tuple[str, ...]
    label: str


class SupportedEngine(StrEnum):
    """The engines this server can reach, in declaration order.

    The declaration order is the order the registry and the tools report
    engines in, so it stays stable across runs.
    """

    POSTGRES = "postgres"
    MARIA = "maria"

    @property
    def _spec(self) -> _EngineSpec:
        """Return the static spec for this engine."""
        return _ENGINE_SPECS[self]

    @property
    def env_var(self) -> str:
        """Return the environment variable that configures this engine."""
        return self._spec.env_var

    @property
    def url_schemes(self) -> tuple[str, ...]:
        """Return the URL schemes (drivers) this engine accepts."""
        return self._spec.url_schemes

    @property
    def alias_schemes(self) -> tuple[str, ...]:
        """Return the plain schemes accepted as aliases for this engine.

        These are rewritten to the engine's single canonical async scheme by the
        registry; they never select a driver on their own.
        """
        return self._spec.alias_schemes

    @property
    def label(self) -> str:
        """Return the human-readable engine name."""
        return self._spec.label

    @classmethod
    def for_env_var(cls, name: str) -> "SupportedEngine | None":
        """Return the engine configured by ``name``, or ``None`` when unknown.

        Matching is exact and case-sensitive on purpose: environment variable
        names are case-sensitive on POSIX, and a near-miss is a typo worth
        reporting rather than silently accepting as a different engine.
        """
        for engine in cls:
            if engine.env_var == name:
                return engine
        return None

    @classmethod
    def env_vars(cls) -> tuple[str, ...]:
        """Return every known connection variable name, in declaration order.

        Callers use this as the allow-list when scanning the environment for
        misspelled ``*_CONNECTION_STRING`` variables.
        """
        return tuple(engine.env_var for engine in cls)


# The single source of truth for env var name, accepted schemes, alias schemes,
# and label. It is defined after the enum so the members already exist; the
# properties on the enum read it lazily at call time, so nothing here runs at
# class creation.
_ENGINE_SPECS: dict[SupportedEngine, _EngineSpec] = {
    SupportedEngine.POSTGRES: _EngineSpec(
        env_var="POSTGRES_CONNECTION_STRING",
        url_schemes=("postgresql+asyncpg",),
        alias_schemes=("postgresql", "postgres"),
        label="PostgreSQL",
    ),
    SupportedEngine.MARIA: _EngineSpec(
        env_var="MARIA_CONNECTION_STRING",
        url_schemes=("mysql+aiomysql",),
        alias_schemes=("mysql", "mariadb"),
        label="MySQL/MariaDB",
    ),
}
