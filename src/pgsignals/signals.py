from django.dispatch import Signal


pgsignals_event = Signal(providing_args=["event"])
