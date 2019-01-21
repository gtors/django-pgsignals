from django.core.management.base import BaseCommand
from ...utils import listen



class Command(BaseCommand):

    help = 'Runs listener of postgresql events'


    def handle(self, *args, **options):
        """
        Runs listener of the postgresql events as foreground process

        Example::

            python manage.py runpgsignals

        """
        print("Run PostgreSQL listener...")
        listen()
