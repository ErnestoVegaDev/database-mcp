"""Map SQLAlchemy column types onto the domain's logical ``ColumnType``.

The domain speaks in logical types (``ColumnType.INTEGER``, ``ColumnType.TEXT``),
while the database speaks in dialect types (``INTEGER``, ``VARCHAR``, ``BLOB``).
This module is the single translation table between the two, so no other layer
ever inspects a SQLAlchemy type.

The table is an ORDERED list of ``isinstance`` probes. Order matters only when
one probe class is a subclass of another and the two map to DIFFERENT domain
types: the narrower rule must win. The ordering below was verified empirically
against SQLAlchemy 2.1.4 rather than assumed, because the class hierarchy is
surprising:

* ``Integer`` does NOT subclass ``Numeric`` (both descend from
  ``HasExpressionLookup`` as siblings), so an ``INTEGER`` check placed before the
  ``Numeric``/``Float`` check is defensive, not strictly required.
* ``TIMESTAMP`` DOES subclass ``DateTime``, so the ``DateTime`` probe already
  catches ``TIMESTAMP``; the two share one domain type (``TIMESTAMP``) anyway.
* ``DateTime`` is NOT a subclass of ``Date`` and vice versa, so those two probes
  cannot shadow each other.
* ``LargeBinary``, ``BINARY`` and ``VARBINARY`` are siblings under the private
  ``_Binary`` base and share NO public superclass. A single check cannot cover
  all three, so each public class is listed explicitly.
* ``Text``, ``Unicode``, ``Enum`` and ``VARCHAR`` all subclass ``String``, so the
  one ``String`` probe covers every text-like column.
"""

from sqlalchemy import types as sa_types

from domain.enums import ColumnType

# Ordered (SQLAlchemy type, domain type) probes. The first probe whose class the
# value is an instance of wins, so a broader rule must never sit above a narrower
# one that maps somewhere else. All "float-like" spellings (Numeric, Float, REAL,
# DOUBLE) resolve to FLOAT through the Numeric/Float probes, because REAL and
# DOUBLE descend from Float and Numeric covers exact-decimal columns.
_TYPE_RULES: tuple[tuple[type, ColumnType], ...] = (
    # Boolean is probed first as a defensive guard: it is a sibling of the
    # integer family today, and if a future SQLAlchemy made it a subclass of
    # Integer, the order here would still keep BOOLEAN from becoming INTEGER.
    (sa_types.Boolean, ColumnType.BOOLEAN),
    # Integer covers SmallInteger, BigInteger and the INTEGER alias, all of
    # which subclass it.
    (sa_types.Integer, ColumnType.INTEGER),
    # Numeric covers exact-decimal columns (NUMERIC, DECIMAL); the domain has no
    # decimal member, so it is declared FLOAT (see D7 for the precision note).
    (sa_types.Numeric, ColumnType.FLOAT),
    # Float covers Float, REAL and DOUBLE (REAL/DOUBLE subclass Float).
    (sa_types.Float, ColumnType.FLOAT),
    # String covers String, Text, Unicode, Enum and VARCHAR; every text-like
    # type in the public API descends from it.
    (sa_types.String, ColumnType.TEXT),
    # DateTime is probed before Date because TIMESTAMP subclasses DateTime, so a
    # TIMESTAMP column would otherwise be mislabeled DATE. DateTime and Date are
    # otherwise unrelated, so this order is what keeps the two apart.
    (sa_types.DateTime, ColumnType.TIMESTAMP),
    (sa_types.Date, ColumnType.DATE),
    # JSON must be probed before the binary probes for clarity only; it shares no
    # ancestry with them. postgresql.JSONB subclasses this base JSON, so it maps
    # here too without importing any dialect-specific module.
    (sa_types.JSON, ColumnType.JSON),
    # The binary family has no shared public base, so every public class is
    # listed: LargeBinary, BINARY and VARBINARY all map to BINARY. A reflected
    # SQLite BLOB subclasses LargeBinary and lands here as well.
    (sa_types.LargeBinary, ColumnType.BINARY),
    (sa_types.BINARY, ColumnType.BINARY),
    (sa_types.VARBINARY, ColumnType.BINARY),
)


def to_column_type(column_type: object) -> ColumnType:
    """Return the logical ``ColumnType`` for a SQLAlchemy type instance.

    Args:
        column_type: Any SQLAlchemy type object, typically
            ``Table.c[name].type`` from a reflected table.

    Returns:
        The first matching logical type, or ``ColumnType.UNKNOWN`` when no probe
        matches (``Time``, ``Uuid``, ``NullType`` and any future type). The
        domain advertises UNKNOWN on purpose instead of guessing, so a caller can
        see that the type is not one the contract understands.
    """
    for sa_class, domain_type in _TYPE_RULES:
        if isinstance(column_type, sa_class):
            return domain_type
    return ColumnType.UNKNOWN
