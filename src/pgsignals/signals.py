from django.dispatch import Signal

__all__ = (
    "pgsignals_event",
    "pgsignals_insert_event",
    "pgsignals_insert_or_update_event",
    "pgsignals_update_event",
    "pgsignals_delete_event",
)

pgsignals_event = Signal(providing_args=["event"])
pgsignals_insert_event = Signal(providing_args=["event"])
pgsignals_insert_or_update_event = Signal(providing_args=["event"])
pgsignals_update_event = Signal(providing_args=["event"])
pgsignals_delete_event = Signal(providing_args=["event"])
