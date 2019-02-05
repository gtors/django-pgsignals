import logging
from collections import Iterable
from django.apps import AppConfig, apps
from django.conf import settings
from django.db.models.signals import post_migrate
from appconf import AppConf


__all__ = (
    "PgsignalsConf",
    "PgsignalsConfig",
)

log = logging.getLogger(__name__)
is_info = log.isEnabledFor(logging.INFO)


class PgsignalsConfig(AppConfig):
    name = 'pgsignals'

    def ready(self):
        # Register triggers after migration completion
        post_migrate.connect(_on_migration_completed, weak=False)



class PgsignalsConf(AppConf):
    PREFIX = 'pgsignals'
    DEFAULT_DATABASE = 'default'
    DEFAULT_SCHEMA = 'public'

    # Timeout in secs for polling connection about new notifies
    POLL_TIMEOUT = 5

    # Example:
    # [
    #   'app.ModelNameA',
    #   ('app.ModelNameB', 'INSERT', 'DELETE'),
    # ]
    OBSERVABLE_MODELS = []


def _on_migration_completed(*args, **kwargs):
    from .utils import bind_model, EventKind

    app_conf = kwargs['app_config']
    app_prefix = f"{app_conf.label}."

    if is_info:
        log.info(f"Apply pgsignals for {app_conf.name}")

    for idx, item in enumerate(settings.PGSIGNALS_OBSERVABLE_MODELS):
        if isinstance(item, str) and item.startswith(app_prefix):
            model = apps.get_model(item)
            bind_model(model)
        elif isinstance(item, Iterable):
            item = tuple(item)

            if len(item) == 0:
                log.warning(f"PGSIGNALS_OBSERVABLE_MODELS[{idx}] is empty")
                continue

            if not isinstance(item[0], str):
                log.warning(f"PGSIGNALS_OBSERVABLE_MODELS[{idx}] "
                            "model name should be str")
                continue

            if not item[0].startswith(app_prefix):
                continue

            model = apps.get_model(item[0])
            events = [getattr(EventKind, ev) for ev in item[1:]]

            if len(events) == 0:
                bind_model(model)
            else:
                bind_model(model, events=events)

