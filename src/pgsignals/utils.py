import functools
import itertools
import logging
import select
import time

from django.apps import apps
from django.conf import settings
from django.db import connections
from typing import Sequence, Optional, Iterable, Dict

from .event import Event
from .enums import EventKind, ALL_EVENTS
from .sql import *


__all__ = (
    "listen",
    "iter_notifies",
    "emit_event",
    "bind_model",
    "unbind_model",
    "bind_table",
    "unbind_table",
)


log = logging.getLogger(__name__)
is_info = log.isEnabledFor(logging.INFO)

PREFIX = settings.PGSIGNALS_PREFIX
DEFAULT_SCHEMA = settings.PGSIGNALS_DEFAULT_SCHEMA
DEFAULT_DATABASE = settings.PGSIGNALS_DEFAULT_DATABASE
DEFAULT_POLL_TIMEOUT = settings.PGSIGNALS_POLL_TIMEOUT


def listen(
        db: str = DEFAULT_DATABASE,
        schema: str = DEFAULT_SCHEMA,
        poll_timeout: int = DEFAULT_POLL_TIMEOUT,
        listen_timeout: Optional[int] = None,
        events_limit: Optional[int] = None,
        once: bool = False) -> None:
    """
    Listen database events

    :param db: Database name
    :param schema: Schema name in database
    :param poll_timeout: Max wait timeout for polling (in seconds)
    :param listen_timeout: Max listen timeout (in seconds)
    :param events_limit: Max events count to listen
    :param once: Handle only first batch of events
    """
    notifies = iter_notifies(
        db=db,
        schema=schema,
        poll_timeout=poll_timeout,
        iter_timeout=listen_timeout,
        once=once)

    if events_limit is not None:
        notifies = itertools.islice(notifies, 0, events_limit)

    for notify in notifies:
        emit_event(notify)


def iter_notifies(
        db: str = DEFAULT_DATABASE,
        schema: str = DEFAULT_SCHEMA,
        poll_timeout: int = DEFAULT_POLL_TIMEOUT,
        iter_timeout: Optional[int] = None,
        once: bool = False) -> Iterable[Event]:
    """
    Create iterator over database events/notifies

    :param db: Database name
    :param schema: Schema name in database
    :param poll_timeout: Max wait timeout for polling (in seconds)
    :param iter_timeout: Max lifetime for iterator (in seconds)
    :param once: If True, then iterator will be stopped after first iteration
    """
    started_at = time.time()

    with connections[db].cursor() as cursor:
        def _count_events():
            cursor.execute(COUNT_EVENTS.format(
                schema=schema,
                prefix=PREFIX
            ))
            return cursor.fetchone()[0]

        # Iterator for extracting events from staging table
        def _iter_events():
            count = _count_events()

            while count != 0:
                cursor.execute(POP_100_EVENTS.format(
                    schema=schema,
                    prefix=PREFIX
                ))

                for (notify,) in cursor:
                    event = _notify_to_event(notify)
                    if event is not None:
                        yield event

                count = _count_events()


        # Emit previously unhandled events
        for event in _iter_events():
            yield event

        # Subscribe to notifications
        conn = cursor.connection
        cursor.execute(f'LISTEN {PREFIX}__events;')

        while True:
            # Check iteration break timeout
            if iter_timeout and (time.time() - started_at) >= iter_timeout:
                break

            # Poll for any new notifies
            if any(select.select([conn],[],[], poll_timeout)):
                conn.poll()

                if len(conn.notifies) > 0:
                    conn.notifies.clear()

                    # Emit new events
                    for event in _iter_events():
                        yield event

            # Handle only first iteration
            if once:
                break


def emit_event(event: Event) -> None:
    """
    Emits Django signal

    :param event: Database event
    """
    from . import signals

    sender = _table_to_model(event.table)
    signals.pgsignals_event.send(
        sender=sender, event=event)

    if event.operation.is_create:
        signals.pgsignals_insert_event.send(
            sender=sender, event=event)

    if event.operation.is_save:
        signals.pgsignals_insert_or_update_event.send(
            sender=sender, event=event)

    if event.operation.is_update:
        signals.pgsignals_update_event.send(
            sender=sender, event=event)

    if event.operation.is_delete:
        signals.pgsignals_delete_event.send(
            sender=sender, event=event)

    if is_info:
        log.info(f"Emit signal for {event.table}, "
                 f"action {event.operation.name},"
                 f"sender {sender}")


def bind_model(
        django_model,
        events: Sequence[EventKind] = ALL_EVENTS,
        db: str = DEFAULT_DATABASE,
        schema: str = DEFAULT_SCHEMA) -> None:
    """
    Bind model for listening

    :param django_model: Model class
    :param events: Specifies which events to listen
    :param db: Database name
    :param schema: Schema name in database
    """
    return bind_table(django_model.objects.model._meta.db_table, events)


def unbind_model(
        django_model,
        db: str = DEFAULT_DATABASE,
        schema: str = DEFAULT_SCHEMA) -> None:
    """
    Unbind model from listening

    :param django_model: Model class
    :param db: Database name
    :param schema: Schema name in database
    """
    return unbind_table(django_model.objects.model._meta.db_table)


def bind_table(
        table_name: str,
        events: Sequence[EventKind] = ALL_EVENTS,
        db: str = DEFAULT_DATABASE,
        schema: str = DEFAULT_SCHEMA) -> None:
    """
    Bind table for listening

    :param table_name: Table name in database
    :param events: Specifies which events to listen
    :param db: Database name
    :param schema: Schema name in database
    """
    unbind_table(table_name, db=db, schema=schema)
    if len(events) > 0:
        migrate_pgsignals_once(db, schema)
        operations = ' OR '.join(ev.value for ev in events)
        sql = CREATE_TRIGGER.format(
            prefix=PREFIX,
            schema=schema,
            table=table_name,
            operations=operations
        )
        _execute_sql(sql, db=db)

        if is_info:
            _events = [ev.name for ev in events]
            log.info(f"Start listen table {table_name} for {_events}")


def unbind_table(
        table_name: str,
        db: str = DEFAULT_DATABASE,
        schema: str = DEFAULT_SCHEMA) -> None:
    """
    Unbind table from listening

    :param table_name: Table name in database
    :param db: Database name
    :param schema: Schema name in database
    """
    sql = DROP_TRIGGER.format(
        prefix=PREFIX,
        schema=schema,
        table=table_name)

    _execute_sql(sql, db=db)

    if is_info:
        log.info(f"Mute table {table_name}")


__migrated: bool = False
def migrate_pgsignals_once(
        db: str = DEFAULT_DATABASE,
        schema: str = DEFAULT_SCHEMA) -> None:

    global __migrated

    if not __migrated:
        migrate_pgsignals(db, schema)
        __migrated = True


def migrate_pgsignals(
        db: str = DEFAULT_DATABASE,
        schema: str = DEFAULT_SCHEMA) -> None:

    sql = CREATE_STAGING_TABLE.format(
        prefix=PREFIX,
        schema=schema)

    _execute_sql(sql, db=db)

    sql = CREATE_EMIT_FUNC.format(
        prefix=PREFIX,
        schema=schema)

    _execute_sql(sql, db=db)

    if is_info:
        log.info("Create staging table and the trigger function")


def _execute_sql(sql: str, db: str) -> None:
    with connections[db].cursor() as cursor:
        cursor.execute(sql)


@functools.lru_cache()
def _table_to_model(table_name: str):
    for model in apps.get_models(include_auto_created=True):
        if model._meta.db_table == table_name:
            return model
    log.error(f"Cannot found model for table {table_name}")
    return None


def _notify_to_event(notify: Dict) -> Event:
    return Event(**{
        **notify,
        "operation": EventKind(notify["operation"])
    })
