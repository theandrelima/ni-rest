"""
Django application initialization with Celery integration.
"""

# TODO: This monkey patch is a temporary fix for compatibility with Python 3.10+
# where collections.Iterable was moved to collections.abc.Iterable.
# This affects older versions of NAPALM and other libraries.
# Remove this once all dependencies have been updated to be compatible with Python 3.10+
import collections
import collections.abc

# Monkey patch for libraries that try to import from collections in Python 3.10+
for name in ['Iterable', 'Mapping', 'Sequence']:
    if not hasattr(collections, name):
        setattr(collections, name, getattr(collections.abc, name))

# This will make sure the app is always imported when
# Django starts so that shared_task will use this app.
from ni_rest.core.celery import app as celery_app

__all__ = ('celery_app',)