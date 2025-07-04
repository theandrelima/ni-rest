"""
Celery tasks for network import operations.

This module contains all asynchronous tasks for the NI-REST API.
Tasks execute immediately when workers are available.
"""

from typing import Any
from datetime import timedelta
from django.utils import timezone
from django.core.exceptions import ValidationError
from celery import shared_task
from celery.utils.log import get_task_logger

from .models import NetworkImporterJob, JobLog
from .services.config_generator import NetworkImporterConfigGenerator
from .services.ni_service import NetworkImporterService

# Use Celery's logger for task logging
logger = get_task_logger(__name__)

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def execute_network_import_task(self, job_id: str, check: bool = False) -> dict[str, Any]:
    """
    Execute network import as a Celery task.
    
    Args:
        job_id: UUID string of the NetworkImporterJob
        check: If True, run in check mode (diff only)
        
    Returns:
        Dictionary with execution results
        
    Raises:
        Retry: If task should be retried due to transient failure
    """
    logger.info(f"Starting network import task for job {job_id}")
    
    try:
        # Get the job
        job = NetworkImporterJob.objects.get(id=job_id)
        
        # Update task ID and status for tracking
        job.celery_task_id = self.request.id
        job.status = 'running'
        job.started_at = timezone.now()
        job.save()
        
        # Generate config dictionary
        config_gen = NetworkImporterConfigGenerator(job.site_code)
        config_dict = config_gen.generate_config_dict(job.config_data)
        
        # Execute with direct Python integration
        service = NetworkImporterService(job, config_dict)
        result = service.run(check=check)
        
        # Update job status on completion
        job.status = 'completed'
        job.completed_at = timezone.now()
        job.save()
        
        logger.info(f"Network import task completed for job {job_id}")
        return result
        
    except NetworkImporterJob.DoesNotExist:
        logger.error(f"Job {job_id} not found")
        return {'success': False, 'error': 'Job not found'}
        
    except ValidationError as e:
        logger.error(f"Validation error in job {job_id}: {str(e)}")
        job = NetworkImporterJob.objects.get(id=job_id)
        job.status = 'failed'
        job.completed_at = timezone.now()
        job.save()
        return {'success': False, 'error': str(e)}
        
    except Exception as exc:
        logger.error(f"Task failed for job {job_id}: {str(exc)}")
        
        # Update job status on failure
        try:
            job = NetworkImporterJob.objects.get(id=job_id)
            job.status = 'failed'
            job.completed_at = timezone.now()
            job.save()
        except NetworkImporterJob.DoesNotExist:
            pass
        
        # Retry on transient failures
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying task for job {job_id} (attempt {self.request.retries + 1})")
            raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
        
        return {'success': False, 'error': str(exc)}

@shared_task
def cleanup_old_jobs_task(days_old: int = 30) -> dict[str, Any]:
    """
    Clean up old jobs and their logs.
    
    Args:
        days_old: Delete jobs older than this many days
        
    Returns:
        Dictionary with cleanup statistics
    """
    logger.info(f"Starting cleanup of jobs older than {days_old} days")
    
    cutoff_date = timezone.now() - timedelta(days=days_old)
    
    # Get old jobs
    old_jobs = NetworkImporterJob.objects.filter(created_at__lt=cutoff_date)
    job_count = old_jobs.count()
    
    # Count logs before deletion
    log_count = JobLog.objects.filter(job__in=old_jobs).count()
    
    # Delete (cascade will handle logs)
    old_jobs.delete()
    
    logger.info(f"Cleanup completed: deleted {job_count} jobs and {log_count} logs")
    
    return {
        'success': True,
        'jobs_deleted': job_count,
        'logs_deleted': log_count,
        'cutoff_date': cutoff_date.isoformat()
    }

@shared_task
def get_job_status_task(job_id: str) -> dict[str, Any]:
    """
    Get current status of a job (useful for polling).
    
    Args:
        job_id: UUID string of the NetworkImporterJob
        
    Returns:
        Dictionary with job status information
    """
    try:
        job = NetworkImporterJob.objects.get(id=job_id)
        return {
            'success': True,
            'job_id': str(job.id),
            'status': job.status,
            'created_at': job.created_at.isoformat(),
            'started_at': job.started_at.isoformat() if job.started_at else None,
            'completed_at': job.completed_at.isoformat() if job.completed_at else None,
            'has_errors': job.has_errors,
            'log_count': job.logs.count()
        }
    except NetworkImporterJob.DoesNotExist:
        return {'success': False, 'error': 'Job not found'}