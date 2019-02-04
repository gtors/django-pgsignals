import enum


__all__ = ("EventKind", "ALL_EVENTS")


class EventKind(enum.Enum):
    INSERT = 'INSERT'
    UPDATE = 'UPDATE'
    DELETE = 'DELETE'

    @property
    def is_create(self) -> bool:
        return self is self.INSERT

    @property
    def is_update(self) -> bool:
        return self is self.UPDATE

    @property
    def is_save(self) -> bool:
        return self.is_create or self.is_update

    @property
    def is_delete(self) -> bool:
        return self is self.DELETE


ALL_EVENTS = (
    EventKind.INSERT,
    EventKind.UPDATE,
    EventKind.DELETE
)
