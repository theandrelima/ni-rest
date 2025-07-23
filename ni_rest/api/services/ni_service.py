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
            # Load settings directly from our config dict
            self.logger.info("Loading network-importer configuration")
            _settings = load(config_data=self.config_dict)
            
            # Log the sanitized config dict for traceability (keep this for debugging issues)
            sanitized_config = self._get_sanitized_config(self.config_dict)
            self.logger.info(
                "Network-importer config loaded with settings:\n" +
                json.dumps(sanitized_config, indent=2, sort_keys=True)
            )
            
            # Create NetworkImporter instance with correct parameters
            self.logger.info("Creating network-importer instance")
            ni = NetworkImporter(check_mode=check)
            
            # Define the limit filter
            limit = f"site={self.job.site_code}"
            
            # STEP 1: Build the inventory based on the limit
            self.logger.info(f"Building inventory with filter: {limit}")
            ni.build_inventory(limit=limit)
            
            # Log inventory status (useful info, not debugging)
            if hasattr(ni, 'nornir'):
                host_count = len(ni.nornir.inventory.hosts)
                self.logger.info(f"Inventory loaded with {host_count} hosts")
                if host_count == 0:
                    self.logger.warning("No hosts found in inventory - no configs will be fetched")
            
            # STEP 2: Update configurations from devices
            try:
                ni.update_configurations()
                self.logger.info("Device configurations updated successfully")
            except Exception as e:
                self.logger.error(f"Failed to update configurations: {str(e)}", exc_info=True)
                # Continue anyway to see if we can proceed with existing data
            
            # STEP 3: Initialize NetworkImporter
            self.logger.info(f"Initializing network-importer with filter: {limit}")
            try:
                ni.init(limit=limit)
                self.logger.info("Network-importer initialized successfully")
            except Exception as e:
                self.logger.error(f"Failed to initialize network-importer: {str(e)}", exc_info=True)
                raise  # Re-raise as this is a critical error
            
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
        """
        Add database logging to key loggers without disrupting the existing logging system.
        """
        # Don't manipulate existing handlers, just add our handlers to key loggers
        key_loggers = [
            '',  # Root logger
            'network_importer',
            'network_importer.main',
            'bax_network_importer',
            'napalm',
            'nornir',
            'netmiko',
            'ni_rest'
        ]
        
        # Store which loggers we've modified so we can clean up only those
        self._modified_loggers = []
        
        for name in key_loggers:
            logger = logging.getLogger(name)
            # Save original level to restore later
            if not hasattr(self, '_original_levels'):
                self._original_levels = {}
            self._original_levels[name] = logger.level
            
            # Just add our handlers without removing existing ones
            for handler in self.logger.handlers:
                if handler not in logger.handlers:
                    logger.addHandler(handler)
            
            # Ensure debug messages are captured
            logger.setLevel(logging.DEBUG)
            
            # Keep track of which loggers we modified
            self._modified_loggers.append(name)
        
        self.logger.info("Database logging enabled for network-importer")
    
    def _restore_original_logging(self) -> None:
        """
        Remove our handlers from loggers without disrupting the rest of the system.
        """
        try:
            # Only restore loggers we actually modified
            if hasattr(self, '_modified_loggers'):
                for name in self._modified_loggers:
                    logger = logging.getLogger(name)
                    
                    # Remove only our handlers
                    for handler in list(logger.handlers):
                        if handler in self.logger.handlers:
                            logger.removeHandler(handler)
                    
                    # Restore original level
                    if hasattr(self, '_original_levels') and name in self._original_levels:
                        logger.setLevel(self._original_levels[name])
            
            self.logger.info("Database logging handlers removed")
        except Exception as e:
            # Log the error but don't crash
            self.logger.error(f"Error cleaning up logging: {str(e)}")