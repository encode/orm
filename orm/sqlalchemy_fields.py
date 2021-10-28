import ipaddress
import uuid

import sqlalchemy


class GUID(sqlalchemy.TypeDecorator):
    """
    Platform-independent GUID type.

    Uses PostgreSQL's UUID type, otherwise uses
    CHAR(32), storing as stringified hex values.
    """

    impl = sqlalchemy.CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(sqlalchemy.dialects.postgresql.UUID())
        else:
            return dialect.type_descriptor(sqlalchemy.CHAR(32))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value

        if dialect.name == "postgresql":
            return str(value)
        else:
            return value.hex

    def process_result_value(self, value, dialect):
        if value is None:
            return value

        if not isinstance(value, uuid.UUID):
            value = uuid.UUID(value)
        return value


class GenericIP(sqlalchemy.TypeDecorator):
    """
    Platform-independent IP Address type.

    Uses PostgreSQL's INET type, otherwise uses
    CHAR(45), storing as stringified values.
    """

    impl = sqlalchemy.CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(sqlalchemy.dialects.postgresql.INET())
        else:
            return dialect.type_descriptor(sqlalchemy.CHAR(45))

    def process_bind_param(self, value, dialect):
        if value is not None:
            return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value

        if not isinstance(value, (ipaddress.IPv4Address, ipaddress.IPv6Address)):
            value = ipaddress.ip_address(value)
        return value
