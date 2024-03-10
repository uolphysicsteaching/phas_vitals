"""
WSGI config for phas_vitals project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/1.8/howto/deployment/wsgi/
"""

# Python imports
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "phas_vitals.settings.production")

# Python imports
import signal
import sys
import time
import traceback

# Django imports
from django.core.wsgi import get_wsgi_application

try:
    application = get_wsgi_application()
    print("WSGI without exception")
except Exception as err:
    print(f"handling WSGI exception\n{err}\n{traceback.format_exc()}")
    # Error loading applications
    if "mod_wsgi" in sys.modules:
        traceback.print_exc()
        os.kill(os.getpid(), signal.SIGINT)
        time.sleep(2.5)
