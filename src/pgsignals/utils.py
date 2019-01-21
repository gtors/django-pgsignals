import enum
import select
import json

from typing import Sequence
from django.db import connections
from django.db.models import Model
from django.conf import settings


PREFIX = settings.PGSIGNALS_PREFIX
DEFAULT_SCHEMA = settings.PGSIGNALS_DEFAULT_SCHEMA
DEFAULT_DATABASE = settings.PGSIGNALS_DEFAULT_DATABASE

CREATE_EMIT_FUNC = """
    CREATE OR REPLACE FUNCTION "{schema}"."{prefix}__emit_event"()
    RETURNS trigger AS $$
    BEGIN
        PERFORM pg_notify(
            '{prefix}__events',
            json_build_object(
                'txid', txid_current(),
                'operation', TG_OP,
                'table', TG_TABLE_NAME,
                'row_before', row_to_json(OLD),
                'row_after', row_to_json(NEW))::text
        );
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
"""

DROP_TRIGGER = """
    DROP TRIGGER IF EXISTS "{prefix}__{table}" ON "{schema}"."{table}";
"""

CREATE_TRIGGER = """
    CREATE TRIGGER "{prefix}__{table}" AFTER {operations}
    ON "{schema}"."{table}" FOR EACH ROW
    EXECUTE PROCEDURE "{schema}"."{prefix}__emit_event"();
"""


class EventKind(enum.Enum):
    INSERT = 'INSERT'
    UPDATE = 'UPDATE'
    DELETE = 'DELETE'


ALL_EVENTS = (
    EventKind.INSERT,
    EventKind.UPDATE,
    EventKind.DELETE
)


def listen(db=DEFAULT_DATABASE, schema=DEFAULT_SCHEMA) -> None:
    from .signals import pgsignals_event

    with connections[db].cursor() as cursor:
        conn = cursor.connection
        cursor.execute(f'LISTEN {PREFIX}__events;')

        def iter_notifies():
            wait_secs = 5
            while True:
                if any(select.select([conn],[],[], wait_secs)):
                    conn.poll()
                    while conn.notifies:
                        yield conn.notifies.pop()

        for notify in iter_notifies():
            try:
                event = json.loads(notify)
            except (JsonParseError):
                pass
            else:
                pgsignals_event.send(sender=None, event=event)


def bind_model(
        django_model: Model,
        events: Sequence[EventKind] = ALL_EVENTS,
        db: str = DEFAULT_DATABASE,
        schema: str = DEFAULT_SCHEMA) -> None:
    return bind_table(django_model.objects.model._meta.db_table, events)


def unbind_model(
        django_model: Model,
        db: str = DEFAULT_DATABASE,
        schema: str = DEFAULT_SCHEMA) -> None:

    return unbind_table(django_model.objects.model._meta.db_table)


def bind_table(
        table_name: str,
        events: Sequence[EventKind] = ALL_EVENTS,
        db: str = DEFAULT_DATABASE,
        schema: str = DEFAULT_SCHEMA) -> None:

    unbind_table(table_name, db=db, schema=schema)
    if len(events) > 0:
        create_emit_func_once(db, schema)
        operations = ' OR '.join(ev.value for ev in events)
        sql = CREATE_TRIGGER.format(
            prefix=PREFIX,
            schema=schema,
            table=table_name,
            operations=operations
        )
        _execute_sql(sql, db=db)


def unbind_table(
        table_name: str,
        db: str = DEFAULT_DATABASE,
        schema: str = DEFAULT_SCHEMA) -> None:

    sql = DROP_TRIGGER.format(
        prefix=PREFIX,
        schema=schema,
        table=table_name)

    _execute_sql(sql, db=db)


_func_created: bool = False
def create_emit_func_once(
        db: str = DEFAULT_DATABASE,
        schema: str = DEFAULT_SCHEMA) -> None:
    global _func_created
    if not _func_created:
        create_emit_func(db, schema)
        _func_created = True


def create_emit_func(
        db: str = DEFAULT_DATABASE,
        schema: str = DEFAULT_SCHEMA) -> None:

    sql = CREATE_EMIT_FUNC.format(
        prefix=PREFIX,
        schema=schema)

    _execute_sql(sql, db=db)


def _execute_sql(sql: str, db: str) -> None:
    with connections[db].cursor() as cursor:
        cursor.execute(sql)
