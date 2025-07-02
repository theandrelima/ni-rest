"""
Utility functions for the NI-REST API.
"""

import logging
from typing import Any
from celery import current_app
from django.conf import settings

logger = logging.getLogger(__name__)

class CeleryWorkerManager:
    """Utility to detect and manage Celery workers"""
    
    @staticmethod
    def get_active_workers() -> dict[str, Any]:
        """
        Get information about active Celery workers.
        
        Returns:
            Dictionary with worker information or empty dict if none available
        """
        try:
            # Use Celery's inspect to check for active workers
            inspect = current_app.control.inspect(timeout=2.0)
            active_workers = inspect.active()
            
            if active_workers:
                return active_workers
            else:
                return {}
                
        except Exception as e:
            logger.debug(f"Could not connect to Celery workers: {e}")
            return {}
    
    @staticmethod
    def has_workers() -> bool:
        """Check if any Celery workers are available"""
        workers = CeleryWorkerManager.get_active_workers()
        return len(workers) > 0
    
    @staticmethod
    def get_worker_count() -> int:
        """Get the number of active workers"""
        workers = CeleryWorkerManager.get_active_workers()
        return len(workers)
    
    @staticmethod
    def should_use_eager_mode() -> bool:
        """Determine if tasks should run in eager mode (no workers available)"""
        # Check if explicitly set to eager mode
        if getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False):
            return True
        
        # Check if workers are available
        return not CeleryWorkerManager.has_workers()