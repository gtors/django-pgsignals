from django.apps import AppConfig
from appconf import AppConf


class PgsignalsConfig(AppConfig):
    name = 'pgsignals'


class PgsignalsConf(AppConf):
    PREFIX = 'pgsignals'
    DEFAULT_DATABASE = 'default'
    DEFAULT_SCHEMA = 'public'

