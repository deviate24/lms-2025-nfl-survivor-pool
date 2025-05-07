from django.apps import AppConfig


class PoolConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'pool'
    
    def ready(self):
        # Import signals when app is ready
        import pool.signals
