import dataclasses
from typing import Dict, Any
from .enums import EventKind

__all__ = ("Event",)


@dataclasses.dataclass
class Event:
    txid: int
    operation: EventKind
    table: str
    row_before: Dict[str, Any]
    row_after: Dict[str, Any]
