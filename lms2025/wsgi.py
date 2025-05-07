"""
WSGI config for lms2025 project.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lms2025.settings')

application = get_wsgi_application()
