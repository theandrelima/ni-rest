# TODO (when the time comes)
# Use Celery to Buffer and Insert Logs
# Rather than writing each log to the DB immediately:
# - Queue each log message as a Celery task (log_job_event.delay(...)).
# - Have Celery insert it into the DB asynchronously.

# This provides:
# - Async log persistence
# - No pressure on the request/worker thread
# - Still ensures logs go through Django ORM (with full model access)

# Extra-step: buffer logs and insert in groups of 10–100 to reduce writes.

import logging
from ..models import NetworkImporterJob, JobLog

class DatabaseLogHandler(logging.Handler):
    """Custom logging handler that writes logs to JobLog model"""
    
    def __init__(self, job: NetworkImporterJob):
        super().__init__()
        self.job = job
    
    def emit(self, record: logging.LogRecord) -> None:
        """Save log record to database"""
        try:
            message = self.format(record)
            level = record.levelname
            
            # Save to database
            JobLog.objects.create(
                job=self.job,
                level=level,
                message=message,
                source=record.name  # Logger name (e.g., 'network_importer.core')
            )
        except Exception:
            # Don't let logging errors break the application
            self.handleError(record)

class JobLogger:
    """Factory for creating job-specific loggers that capture all Network Importer output"""
    
    @staticmethod
    def create_logger(job: NetworkImporterJob, logger_name: str = 'ni_rest') -> logging.Logger:
        """Create a logger that writes to both console and database"""
        logger = logging.getLogger(f"{logger_name}.job_{job.id}")
        logger.setLevel(logging.DEBUG)
        logger.handlers.clear()
        
        # Add console handler for development/debugging
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter(
            f'[JOB-{job.id}] %(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
        
        # Add database handler for persistence
        db_handler = DatabaseLogHandler(job)
        db_formatter = logging.Formatter('%(message)s')  # Simple format for DB
        db_handler.setFormatter(db_formatter)
        logger.addHandler(db_handler)
        
        return logger