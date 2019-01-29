# Django PostgreSQL Signals

This django app allows you to pass events about database changes directly into Djano as regular signal.


# Install

## Pypi

```
pip install pgsignals
```

# Usage

**settings.py**
```
INSTALLED_APPS = [
    "pgsignals",
    ...
]

PGSIGNALS_OBSERVABLE_MODELS = [
    "myapp.ModelA",
    "myapp.ModelB",
]
```

**apps.py**
```
from pgsignals.signals import pgsignals_event

class MyAppConf(AppConf):

    def ready():
        pgsignals_event.connect(on_pg_event)


def on_pg_event(*args, **kwargs):
    event = kwargs['event']
    model = kwargs['sender']
    # Do some useful stuff here
```
