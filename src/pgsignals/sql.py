__all__ = (
    "CREATE_STAGING_TABLE",
    "POP_EVENT",
    "CREATE_EMIT_FUNC",
    "DROP_TRIGGER",
    "CREATE_TRIGGER",
)


CREATE_STAGING_TABLE = """
    CREATE TABLE IF NOT EXISTS "{schema}"."{prefix}__events" (
        ts TIMESTAMPTZ DEFAULT now(),
        payload JSONB
    );
"""


POP_EVENT = """
    DELETE FROM "{schema}"."{prefix}__events"
    WHERE ts = (SELECT MAX(ts) FROM "{schema}"."{prefix}__events")
    RETURNING payload;
"""


CREATE_EMIT_FUNC = """
    CREATE OR REPLACE FUNCTION "{schema}"."{prefix}__emit_event"()
    RETURNS trigger AS $$
    DECLARE
        payload jsonb;
        oldx jsonb := null;
        newx jsonb := null;
    BEGIN
        IF (TG_OP = 'DELETE') THEN
            oldx := to_jsonb(OLD);
        ELSIF (TG_OP = 'INSERT') THEN
            newx := to_jsonb(NEW);
        ELSIF (TG_OP = 'UPDATE') THEN
            oldx := to_jsonb(OLD);
            newx := to_jsonb(NEW);
        END IF;

        payload := jsonb_build_object(
            'txid', txid_current(),
            'operation', TG_OP,
            'table', TG_TABLE_NAME,
            'row_before', oldx,
            'row_after', newx);
        INSERT INTO "{schema}"."{prefix}__events" (ts, payload)
        VALUES (now(), payload);

        PERFORM pg_notify('{prefix}__events', '');

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


