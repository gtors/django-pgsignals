from django.core.management.base import BaseCommand
from ..utils import listen



class DaemonCommand(BaseCommand):
        
    help = 'Runs listener of postgresql events'
    
    
    def handle(self, *args, **options):
        """
        Runs listener of the postgresql events as foreground process

        Example::
        
            python manage.py listen_pgsignals 
        
        """
        listen()
