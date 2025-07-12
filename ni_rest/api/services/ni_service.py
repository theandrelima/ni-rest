import logging
from typing import Any, Dict
from django.utils import timezone
from network_importer.config import load
from network_importer.main import NetworkImporter
from ..models import NetworkImporterJob
from .job_logger import JobLogger
import json
import copy

class NetworkImporterService:
    """Execute network-importer with direct Python integration and database logging"""
    
    def __init__(self, job: NetworkImporterJob, config_dict: dict[str, Any]):
        self.job = job
        self.config_dict = config_dict
        self.logger = JobLogger.create_logger(job)
        
        # Hijack network-importer logging IMMEDIATELY in constructor
        self._hijack_network_importer_logging()
    
    def run(self, check: bool = False) -> dict[str, Any]:
        """Execute network-importer with Python integration"""
        
        # Update job status
        self.job.status = 'running'
        self.job.started_at = timezone.now()
        mode = 'check' if check else 'apply'
        self.job.save()
        
        self.logger.info(f"Starting network import ({mode} mode) for site: {self.job.site_code}")
        
        try:
            self.logger.debug("Loading network-importer configuration")
            
            # Create a sanitized copy of the config dict for logging
            sanitized_config = self._get_sanitized_config(self.config_dict)
            
            # Log the sanitized config dict as JSON for traceability
            self.logger.info(
                "Final network-importer config (as used by network-importer):\n" +
                json.dumps(sanitized_config, indent=2, sort_keys=True)
            )
            
            # Load settings directly from our config dict
            _settings = load(config_data=self.config_dict)
            
            self.logger.info("Creating network-importer instance")
            
            # Create NetworkImporter instance with correct parameters
            ni = NetworkImporter(check_mode=check)
            
            # Execute based on mode
            if check:
                result = self._execute_check(ni)
            else:
                result = self._execute_apply(ni)
            
            # Determine success
            success = result.get('success', True) if result else True
            
            # Update job status
            self.job.status = 'completed' if success else 'failed'
            self.job.completed_at = timezone.now()
            self.job.save()
            
            if success:
                self.logger.info(f"Network import ({mode}) completed successfully")
            else:
                self.logger.error(f"Network import ({mode}) completed with errors")
            
            return {
                "success": success,
                "message": f"{mode.capitalize()} completed successfully" if success else f"{mode.capitalize()} completed with errors",
                "result": result
            }
            
        except Exception as e:
            self.job.status = 'failed'
            self.job.completed_at = timezone.now()
            self.job.save()
            
            self.logger.error(f"Network import failed: {str(e)}", exc_info=True)
            
            return {
                "success": False,
                "error": str(e),
                "message": "Import failed"
            }

        finally:
            # Clean up logging hijack
            self._restore_original_logging()

    def _get_sanitized_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a sanitized copy of the config dict with sensitive data masked.
        
        Args:
            config: Original configuration dictionary
            
        Returns:
            Sanitized copy with sensitive data masked
        """
        # Create a deep copy to avoid modifying the original
        sanitized = copy.deepcopy(config)
        
        # Mask inventory token if present
        if 'inventory' in sanitized and isinstance(sanitized['inventory'], dict):
            if 'settings' in sanitized['inventory'] and isinstance(sanitized['inventory']['settings'], dict):
                if 'token' in sanitized['inventory']['settings']:
                    sanitized['inventory']['settings']['token'] = '********'
        
        # Mask network password if present
        if 'network' in sanitized and isinstance(sanitized['network'], dict):
            if 'password' in sanitized['network']:
                sanitized['network']['password'] = '********'
        
        return sanitized
    
    def _execute_check(self, ni: NetworkImporter) -> dict[str, Any]:
        """Execute network-importer in check mode (calculate diffs only)"""
        self.logger.info("Executing network check (diff calculation)...")
        
        # Initialize the importer - this will log to our database
        ni.init()
        
        # Calculate diff without applying changes - this will log to our database
        diff = ni.diff()
        
        self.logger.info("Check mode completed - differences calculated")
        
        return {
            "success": True,
            "mode": "check",
            "diff": str(diff) if diff else "No differences found",
            "changes_detected": bool(diff)
        }
    
    def _execute_apply(self, ni: NetworkImporter) -> dict[str, Any]:
        """Execute network-importer in apply mode (calculate diffs and apply changes)"""
        self.logger.info("Executing network apply (diff calculation + sync)...")
        
        # Initialize the importer - this will log to our database
        ni.init()
        
        # Calculate diff first - this will log to our database
        diff = ni.diff()
        
        if diff:
            self.logger.info(f"Changes detected:\n{diff}")
            # Apply the changes - this will log to our database
            ni.sync()
            self.logger.info("Changes applied successfully")
        else:
            self.logger.info("No changes to apply")
        
        return {
            "success": True,
            "mode": "apply",
            "diff": str(diff) if diff else "No differences found",
            "changes_applied": bool(diff)
        }
    
    def _hijack_network_importer_logging(self) -> None:
        """Replace network-importer loggers with our database logger"""
        
        # Store original handlers for restoration
        self._original_handlers = {}
        self._original_propagate = {}
        
        # Only hijack specific network-importer loggers, not root logger
        ni_logger_names = [
            'network_importer',
            'network_importer.core',
            'network_importer.main',
            'network_importer.adapters',
            'network_importer.drivers',
            'network_importer.models',
            'network_importer.config',
            'network_importer.utils'
        ]
        
        # Replace each logger
        for logger_name in ni_logger_names:
            ni_logger = logging.getLogger(logger_name)
            
            # Store original handlers and propagate setting
            self._original_handlers[logger_name] = ni_logger.handlers.copy()
            self._original_propagate[logger_name] = ni_logger.propagate
            
            # Replace with our handlers
            ni_logger.handlers.clear()
            for handler in self.logger.handlers:
                ni_logger.addHandler(handler)
            
            ni_logger.setLevel(logging.DEBUG)
            ni_logger.propagate = False  # Prevent double logging
        
        self.logger.info("Network-importer logging redirected to NI-REST database")
    
    def _restore_original_logging(self) -> None:
        """Restore original logging configuration"""
        
        if hasattr(self, '_original_handlers'):
            for logger_name, original_handlers in self._original_handlers.items():
                ni_logger = logging.getLogger(logger_name)
                ni_logger.handlers.clear()
                
                # Restore original handlers
                for handler in original_handlers:
                    ni_logger.addHandler(handler)
                
                # Restore original propagate setting
                if logger_name in self._original_propagate:
                    ni_logger.propagate = self._original_propagate[logger_name]
        
        self.logger.info("Original logging configuration restored")