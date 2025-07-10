"""
Celery configuration for ni_rest project.

This module sets up Celery for asynchronous task processing with graceful fallback.
"""

import os
from celery import Celery
from django.conf import settings

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ni_rest.core.settings')

app = Celery('ni_rest')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

@app.task(bind=True, ignore_result=True)
def debug_task(self) -> str:
    """Debug task for testing Celery connectivity."""
    return f'Request: {self.request!r}'