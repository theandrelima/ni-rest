import tempfile
import toml
import os
from pathlib import Path
from typing import Any
from django.conf import settings
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404

from ..models import (
    NetworkImporterInventorySettings,
    NetworkImporterNetCreds,
    BatfishServiceSetting
)

class NetworkImporterConfigGenerator:
    """
    Generate network_importer.toml configuration from REST API payload.
    
    This class converts a structured dictionary payload into a valid network-importer
    TOML configuration file. It uses Django models to manage sensitive credentials
    and service configurations.
    
    Example config_data payload (user-provided):
    {
        "main": {
            "import_ips": True,
            "import_prefixes": True,
            "import_cabling": "cdp",
            "backend": "nautobot",
            "nbr_workers": 10
        },
        "inventory": {
            "supported_platforms": ["cisco_ios", "cisco_asa"],
            "settings_name": "production_nautobot"  # References NetworkImporterInventorySettings
        },
        "network": {
            "fqdns": ["example.com"],
            "credentials_name": "network_admin",  # References NetworkImporterNetCreds
            "netmiko_extras": {
                "global_delay_factor": 15,
                "banner_timeout": 5
            }
        },
        "logs": {
            "level": "info",
            "performance_log": True
        },
        "adapters": {
            "network_class": "custom.NetworkAdapter",
            "sot_class": "custom.NautobotAdapter"
        },
        "drivers": {
            "mapping": {
                "cisco_ios": "custom.cisco_ios_driver"
            }
        },
        "batfish_setting": "production"  # Optional: References BatfishServiceSetting by name
    }
    
    Note: Batfish configuration is automatically resolved from BatfishServiceSetting model.
    If "batfish_setting" is not provided, uses the first available BatfishServiceSetting.
    """
    
    # Default driver mappings - defined once as class constant
    DEFAULT_DRIVER_MAPPINGS = {
        "default": "network_importer.drivers.default",
        "cisco_asa": "network_importer.drivers.cisco_asa",
        "cisco_nxos": "network_importer.drivers.cisco_default",
        "cisco_ios": "network_importer.drivers.cisco_default",
        "cisco_xr": "network_importer.drivers.cisco_default",
        "juniper_junos": "network_importer.drivers.juniper_junos",
        "arista_eos": "network_importer.drivers.arista_eos"
    }
    
    def __init__(self, site_code: str):
        """
        Initialize the config generator for a specific site.
        
        Args:
            site_code: Site identifier used for temporary file naming
        """
        self.site_code = site_code
    
    def generate_config_file(self, config_data: dict[str, Any]) -> Path:
        """
        Generate temporary config file for network-importer.
        
        Args:
            config_data: Dictionary containing user-provided network-importer configuration
            
        Returns:
            Path to the generated temporary TOML configuration file
            
        Raises:
            OSError: If temporary file creation fails
            TypeError: If config_data contains invalid types for TOML serialization
            ValidationError: If referenced models don't exist or have invalid env vars
        """
        
        # Base configuration structure with comprehensive sections
        config = {
            "main": self._get_main_config(config_data.get("main", {})),
            "inventory": self._get_inventory_config(config_data.get("inventory", {})),
            "network": self._get_network_config(config_data.get("network", {})),
            "logs": self._get_logs_config(config_data.get("logs", {}))
        }
        
        # Always include Batfish configuration (internal service)
        config["batfish"] = self._get_batfish_config_internal(config_data.get("batfish_setting"))
        
        # Always include drivers configuration (with defaults)
        config["drivers"] = self._get_drivers_config(config_data.get("drivers", {}))
        
        # Add optional user-configurable sections if provided
        if "adapters" in config_data:
            config["adapters"] = self._get_adapters_config(config_data["adapters"])
        
        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(
            mode='w', 
            suffix='.toml', 
            prefix=f'ni-{self.site_code}-',
            delete=False
        )
        
        toml.dump(config, temp_file)
        temp_file.flush()
        
        return Path(temp_file.name)
    
    def _get_main_config(self, main_data: dict[str, Any]) -> dict[str, Any]:
        """
        Get main configuration section with defaults.
        
        Args:
            main_data: Main section configuration data
            
        Returns:
            Dictionary with main configuration including defaults
        """
        return {
            "import_ips": main_data.get("import_ips", True),
            "import_prefixes": main_data.get("import_prefixes", True),
            "import_cabling": main_data.get("import_cabling", "cdp"),
            "import_intf_status": main_data.get("import_intf_status", False),
            "import_vlans": main_data.get("import_vlans", "cli"),
            "backend": main_data.get("backend", "nautobot"),
            "nbr_workers": main_data.get("nbr_workers", 10)
        }
    
    def _get_inventory_config(self, inventory_data: dict[str, Any]) -> dict[str, Any]:
        """
        Get inventory configuration using NetworkImporterInventorySettings model.
        
        Args:
            inventory_data: Inventory section configuration data
                          Must contain 'settings_name' referencing a NetworkImporterInventorySettings
            
        Returns:
            Dictionary with inventory configuration and resolved credentials
            
        Raises:
            ValidationError: If settings_name is missing or invalid
        """
        config = {}
        
        # Handle supported platforms
        if "supported_platforms" in inventory_data:
            config["supported_platforms"] = inventory_data["supported_platforms"]
        else:
            config["supported_platforms"] = ["cisco_ios", "cisco_asa", "cisco_nxos", "juniper_junos", "arista_eos"]
        
        # Get settings from model
        settings_name = inventory_data.get("settings_name")
        if not settings_name:
            raise ValidationError("inventory.settings_name is required")
        
        try:
            inventory_settings = get_object_or_404(NetworkImporterInventorySettings, name=settings_name)
        except Exception as e:
            raise ValidationError(f"Invalid inventory settings_name '{settings_name}': {str(e)}")
        
        # Build settings configuration
        try:
            config["settings"] = {
                "address": inventory_settings.address,
                "token": inventory_settings.token,  # This will access the property
                "verify_ssl": inventory_settings.verify_ssl,
                "timeout": inventory_data.get("timeout", 30),
                "page_size": inventory_data.get("page_size", 1000),
                "max_workers": inventory_data.get("max_workers", 10)
            }
        except ValidationError as e:
            raise ValidationError(f"Error accessing inventory settings for '{settings_name}': {str(e)}")
        
        return config
    
    def _get_network_config(self, network_data: dict[str, Any]) -> dict[str, Any]:
        """
        Get network configuration using NetworkImporterNetCreds model.
        
        Args:
            network_data: Network section configuration data
                         Must contain 'credentials_name' referencing a NetworkImporterNetCreds
            
        Returns:
            Dictionary with network configuration and resolved credentials
            
        Raises:
            ValidationError: If credentials_name is missing or invalid
        """
        config = {}
        
        # Handle FQDNs
        config["fqdns"] = network_data.get("fqdns", [])
        
        # Get credentials from model
        credentials_name = network_data.get("credentials_name")
        if not credentials_name:
            raise ValidationError("network.credentials_name is required")
        
        try:
            net_creds = get_object_or_404(NetworkImporterNetCreds, name=credentials_name)
        except Exception as e:
            raise ValidationError(f"Invalid network credentials_name '{credentials_name}': {str(e)}")
        
        # Build network configuration with credentials
        try:
            config["login"] = net_creds.login      # This will access the property
            config["password"] = net_creds.password  # This will access the property
        except ValidationError as e:
            raise ValidationError(f"Error accessing network credentials for '{credentials_name}': {str(e)}")
        
        # Handle optional enable field
        if "enable" in network_data:
            config["enable"] = network_data["enable"]
        
        # Handle netmiko_extras subsection
        if "netmiko_extras" in network_data:
            config["netmiko_extras"] = {
                "global_delay_factor": network_data["netmiko_extras"].get("global_delay_factor", 15),
                "banner_timeout": network_data["netmiko_extras"].get("banner_timeout", 5),
                "conn_timeout": network_data["netmiko_extras"].get("conn_timeout", 5),
                "session_timeout": network_data["netmiko_extras"].get("session_timeout", 60),
                "keepalive": network_data["netmiko_extras"].get("keepalive", 30)
            }
        
        return config
    
    def _get_logs_config(self, logs_data: dict[str, Any]) -> dict[str, Any]:
        """
        Get logs configuration with defaults.
        
        Args:
            logs_data: Logs section configuration data
            
        Returns:
            Dictionary with logs configuration including defaults
        """
        return {
            "level": logs_data.get("level", "info"),
            "performance_log": logs_data.get("performance_log", False),
            "file": logs_data.get("file", f"/tmp/ni-{self.site_code}.log"),
            "format": logs_data.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"),
            "max_file_size": logs_data.get("max_file_size", "10MB"),
            "backup_count": logs_data.get("backup_count", 5)
        }
    
    def _get_adapters_config(self, adapters_data: dict[str, Any]) -> dict[str, Any]:
        """
        Get adapters configuration.
        
        Args:
            adapters_data: Adapters section configuration data
            
        Returns:
            Dictionary with adapters configuration
        """
        config = {}
        
        # Main adapter classes
        if "network_class" in adapters_data:
            config["network_class"] = adapters_data["network_class"]
        if "sot_class" in adapters_data:
            config["sot_class"] = adapters_data["sot_class"]
        
        # SOT settings subsection
        if "sot_settings" in adapters_data:
            config["sot_settings"] = {
                "warn_on_delete": adapters_data["sot_settings"].get("warn_on_delete", False),
                "model_flag": adapters_data["sot_settings"].get("model_flag", 1),
                "batch_size": adapters_data["sot_settings"].get("batch_size", 100),
                "timeout": adapters_data["sot_settings"].get("timeout", 300)
            }
            
            # Handle optional list fields
            if "model_flag_tags" in adapters_data["sot_settings"]:
                config["sot_settings"]["model_flag_tags"] = adapters_data["sot_settings"]["model_flag_tags"]
        
        return config
    
    def _get_batfish_config_internal(self, batfish_setting_name: str | None = None) -> dict[str, Any]:
        """
        Get Batfish configuration from BatfishServiceSetting model.
        
        Args:
            batfish_setting_name: Optional name of specific BatfishServiceSetting to use.
                                If None, uses the first available BatfishServiceSetting.
        
        Returns:
            Dictionary with Batfish configuration for internal service
            
        Raises:
            ValidationError: If no BatfishServiceSetting is found
        """
        try:
            if batfish_setting_name:
                # Use specified batfish setting
                batfish_settings = get_object_or_404(BatfishServiceSetting, name=batfish_setting_name)
            else:
                # Use first available batfish setting
                batfish_settings = BatfishServiceSetting.objects.first()
                if not batfish_settings:
                    raise ValidationError("No BatfishServiceSetting found in database")
        except Exception as e:
            if batfish_setting_name:
                raise ValidationError(f"Invalid batfish setting name '{batfish_setting_name}': {str(e)}")
            else:
                raise ValidationError(f"Error retrieving batfish settings: {str(e)}")
        
        # Build config with only non-null values
        config = {}
        
        if batfish_settings.address is not None:
            config["address"] = batfish_settings.address
        
        if batfish_settings.network_name is not None:
            config["network_name"] = batfish_settings.network_name
        
        if batfish_settings.snapshot_name is not None:
            config["snapshot_name"] = batfish_settings.snapshot_name
        
        if batfish_settings.port_v1 is not None:
            config["port_v1"] = batfish_settings.port_v1
        
        if batfish_settings.port_v2 is not None:
            config["port_v2"] = batfish_settings.port_v2
        
        if batfish_settings.use_ssl is not None:
            config["use_ssl"] = batfish_settings.use_ssl
        
        return config
    
    def _get_drivers_config(self, drivers_data: dict[str, Any]) -> dict[str, Any]:
        """
        Get drivers configuration with default mappings.
        
        Args:
            drivers_data: Drivers section configuration data
            
        Returns:
            Dictionary with drivers configuration including default mappings
        """
        config = {}
        
        # Start with default mappings
        config["mapping"] = self.DEFAULT_DRIVER_MAPPINGS.copy()
        
        # Override with user-provided mappings if present
        if "mapping" in drivers_data:
            config["mapping"].update(drivers_data["mapping"])
        
        return config
    
    def validate_config(self, config_data: dict[str, Any]) -> dict[str, Any]:
        """
        Enhanced validation of user-provided configuration data.
        
        Args:
            config_data: Configuration dictionary to validate
            
        Returns:
            Dictionary containing:
            - is_valid: Boolean indicating if config is valid
            - errors: List of validation errors
            - warnings: List of validation warnings
            - referenced_models: Dict of referenced model instances
        """
        errors = []
        warnings = []
        referenced_models = {}
        
        # Validate main section
        main_section = config_data.get("main", {})
        
        # Required backend field
        if "backend" not in main_section:
            errors.append("Missing required field: main.backend")
        else:
            valid_backends = ["nautobot", "netbox", "device42", "phpipam"]
            if main_section["backend"] not in valid_backends:
                errors.append(f"Invalid backend '{main_section['backend']}'. Must be one of: {valid_backends}")
        
        # Validate inventory settings reference
        inventory_section = config_data.get("inventory", {})
        if "settings_name" in inventory_section:
            try:
                inventory_settings = NetworkImporterInventorySettings.objects.get(
                    name=inventory_section["settings_name"]
                )
                # Validate token access
                _ = inventory_settings.token
                referenced_models["inventory_settings"] = inventory_settings
            except NetworkImporterInventorySettings.DoesNotExist:
                errors.append(f"Inventory settings '{inventory_section['settings_name']}' not found")
            except ValidationError as e:
                errors.append(f"Inventory settings validation error: {str(e)}")
        else:
            errors.append("Missing required field: inventory.settings_name")
        
        # Validate network credentials reference
        network_section = config_data.get("network", {})
        if "credentials_name" in network_section:
            try:
                net_creds = NetworkImporterNetCreds.objects.get(
                    name=network_section["credentials_name"]
                )
                # Validate credentials access
                _ = net_creds.login
                _ = net_creds.password
                referenced_models["network_credentials"] = net_creds
            except NetworkImporterNetCreds.DoesNotExist:
                errors.append(f"Network credentials '{network_section['credentials_name']}' not found")
            except ValidationError as e:
                errors.append(f"Network credentials validation error: {str(e)}")
        else:
            errors.append("Missing required field: network.credentials_name")
        
        # Validate Batfish service reference
        batfish_setting_name = config_data.get("batfish_setting")
        try:
            if batfish_setting_name:
                batfish_settings = BatfishServiceSetting.objects.get(name=batfish_setting_name)
                referenced_models["batfish_service"] = batfish_settings
            else:
                batfish_settings = BatfishServiceSetting.objects.first()
                if not batfish_settings:
                    errors.append("No BatfishServiceSetting found in database")
                else:
                    referenced_models["batfish_service"] = batfish_settings
        except BatfishServiceSetting.DoesNotExist:
            errors.append(f"Batfish service '{batfish_setting_name}' not found")
        
        # Validate numeric fields with sensible ranges
        numeric_validations = {
            "main.nbr_workers": (1, 50),
            "logs.backup_count": (1, 20),
            "network.netmiko_extras.global_delay_factor": (1, 100),
            "network.netmiko_extras.banner_timeout": (1, 300),
            "network.netmiko_extras.conn_timeout": (1, 300)
        }
        
        for field_path, (min_val, max_val) in numeric_validations.items():
            value = self._get_nested_value(config_data, field_path)
            if value is not None:
                try:
                    num_value = int(value)
                    if not (min_val <= num_value <= max_val):
                        warnings.append(f"Field '{field_path}' value {num_value} is outside recommended range {min_val}-{max_val}")
                except (ValueError, TypeError):
                    errors.append(f"Field '{field_path}' must be a valid integer")
        
        # Validate supported platforms
        supported_platforms = config_data.get("inventory", {}).get("supported_platforms", [])
        valid_platforms = ["cisco_ios", "cisco_asa", "cisco_nxos", "cisco_xr", "juniper_junos", "arista_eos"]
        if supported_platforms:
            invalid_platforms = [p for p in supported_platforms if p not in valid_platforms]
            if invalid_platforms:
                warnings.append(f"Unknown platforms: {invalid_platforms}. Valid platforms: {valid_platforms}")
        
        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "referenced_models": referenced_models
        }
    
    def _get_nested_value(self, data: dict[str, Any], path: str) -> Any:
        """
        Get nested dictionary value using dot notation.
        
        Args:
            data: Dictionary to search
            path: Dot-separated path (e.g., "main.nbr_workers")
            
        Returns:
            Value at the specified path, or None if not found
        """
        keys = path.split('.')
        current = data
        
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        
        return current