from typing import Any
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.utils.crypto import get_random_string
from network_importer.config import DEFAULT_DRIVERS_MAPPING
from ..models import (
    NetworkImporterInventorySettings,
    NetworkImporterNetCreds,
    BatfishServiceSetting
)
import copy

class NetworkImporterConfigGenerator:
    """   
    This class converts a structured dictionary payload into a valid network-importer
    configuration dictionary. It uses Django models to manage sensitive credentials
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
            "name": "production_nautobot"  # References NetworkImporterInventorySettings (changed from settings_name)
        },
        "network": {
            "fqdns": ["example.com"],
            "credentials_name": "network_admin",  # References NetworkImporterNetCreds
            "netmiko_extras": {
                "global_delay_factor": 15,
                "banner_timeout": 5
            }
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
        "batfish": "production"  # Optional: References BatfishServiceSetting by name
    }
    
    Note: Batfish configuration is automatically resolved from BatfishServiceSetting model.
    If "batfish" is not provided, uses the first available BatfishServiceSetting.
    User log configs are completely ignored - NI-REST controls logging entirely.
    """

    def __init__(self, site_code: str):
        """
        Initialize the config generator for a specific site.
        
        Args:
            site_code: Site identifier used for naming purposes
        """
        self.site_code = site_code

    def generate_config_dict(self, config_data: dict[str, Any]) -> dict[str, Any]:
        """        
        This method builds the full configuration structure that would normally
        be written to a TOML file, but returns it as a Python dictionary instead.
        
        NO logs section is included - NI-REST controls logging entirely through
        the DatabaseLogHandler system.
        
        Args:
            config_data: Dictionary containing user-provided network-importer configuration
            
        Returns:
            Complete configuration dictionary with all sections and nesting
            that matches the TOML structure expected by network-importer
            
        Raises:
            ValidationError: If referenced models don't exist or have invalid env vars
        """
        # Start with the user-provided configuration as the base
        # This ensures all user-provided settings are preserved
        config = copy.deepcopy(config_data)
        
        # Process required sections with special handling
        self._process_inventory_section(config)
        self._process_network_section(config)
        self._process_batfish_section(config)
        
        # Add defaults for main section if not present
        if 'main' not in config:
            config['main'] = self._get_default_main_config()
            
        # Add defaults for drivers if not present
        if 'drivers' not in config:
            config['drivers'] = {'mapping': DEFAULT_DRIVERS_MAPPING.copy()}
        elif 'mapping' not in config['drivers']:
            config['drivers']['mapping'] = DEFAULT_DRIVERS_MAPPING.copy()
       
        # Clean up internal reference fields that network-importer doesn't expect
        self._cleanup_internal_reference_fields(config)
        
        return config

    def _cleanup_internal_reference_fields(self, config: dict[str, Any]) -> None:
        """
        Remove internal reference fields that are not expected by network-importer.
        
        Args:
            config: Configuration dictionary to clean up in place
        """
        # Remove inventory.name after it's been used for credential lookup
        if 'inventory' in config and isinstance(config['inventory'], dict):
            config['inventory'].pop('name', None)
            
        # Remove network.credentials_name after it's been used for credential lookup
        if 'network' in config and isinstance(config['network'], dict):
            config['network'].pop('credentials_name', None)
            
        # Remove batfish.name after it's been used for configuration lookup
        if 'batfish' in config and isinstance(config['batfish'], dict):
            config['batfish'].pop('name', None)

    def _get_default_main_config(self) -> dict[str, Any]:
        """Get default main configuration settings."""
        return {
            "import_ips": True,
            "import_prefixes": True,
            "import_cabling": "cdp",
            "import_intf_status": False,
            "import_vlans": "cli",
            "backend": "nautobot",
            "nbr_workers": 10
        }

    def _require_section_and_key_and_model(self, config: dict, section: str, key: str, model_cls, model_field: str):
        """
        Generalized check for section existence, type, key presence, and model lookup.

        Args:
            config: The configuration dictionary.
            section: The section name (e.g., 'inventory').
            key: The key to check within the section (e.g., 'name').
            model_cls: The Django model class to look up.
            model_field: The field name in the model to match.

        Returns:
            (section_obj, model_instance): The section dictionary and the model instance.

        Raises:
            ValidationError: If any check fails or the model instance is not found.
        """
        if section not in config:
            raise ValidationError(f"{section} section is required")

        section_obj = config[section]
        if not isinstance(section_obj, dict):
            raise ValidationError(f"{section} must be a dictionary")

        if key not in section_obj:
            raise ValidationError(f"{section}.{key} is required")

        ref_value = section_obj[key]
        try:
            model_instance = get_object_or_404(model_cls, **{model_field: ref_value})
        except Exception as e:
            raise ValidationError(f"Invalid {section} {key} '{ref_value}': {str(e)}")

        return section_obj, model_instance

    def _process_inventory_section(self, config: dict[str, Any]) -> None:
        """
        Process inventory section, expanding name reference into credentials.

        Args:
            config: Configuration dictionary to modify in place

        Raises:
            ValidationError: If name reference is invalid or credentials not found
        """
        inventory, inventory_settings = self._require_section_and_key_and_model(
            config, 'inventory', 'name', NetworkImporterInventorySettings, 'name'
        )

        # Check if settings section already exists to prevent overwriting user values
        if 'settings' in inventory:
            raise ValidationError(
                "inventory.settings is already defined in the config. "
                "This would conflict with the credentials lookup."
            )

        try:
            inventory_credentials = {
                "address": inventory_settings.address,
                "token": inventory_settings.token,  # This will access the property
                "verify_ssl": inventory_settings.verify_ssl,
            }
            # Add settings to inventory dict
            inventory['settings'] = inventory_credentials
        except ValidationError as e:
            raise ValidationError(f"Error accessing inventory settings for '{inventory['name']}': {str(e)}")

    def _process_network_section(self, config: dict[str, Any]) -> None:
        """
        Process network section, expanding credentials_name into login/password.

        Args:
            config: Configuration dictionary to modify in place

        Raises:
            ValidationError: If credentials_name is invalid or credentials not found
        """
        network, net_creds = self._require_section_and_key_and_model(
            config, 'network', 'credentials_name', NetworkImporterNetCreds, 'name'
        )

        # Check for potential conflicts
        if 'login' in network:
            raise ValidationError(
                "network.login is already defined in the config. "
                "This would conflict with the credentials lookup."
            )

        if 'password' in network:
            raise ValidationError(
                "network.password is already defined in the config. "
                "This would conflict with the credentials lookup."
            )

        try:
            network['login'] = net_creds.login      # This will access the property
            network['password'] = net_creds.password  # This will access the property
        except ValidationError as e:
            raise ValidationError(f"Error accessing network credentials for '{network['credentials_name']}': {str(e)}")

    def _process_batfish_section(self, config: dict[str, Any]) -> None:
        """
        Process batfish section if present, or add default batfish settings if not.

        Args:
            config: Configuration dictionary to modify in place

        Raises:
            ValidationError: If batfish name reference is invalid
        """
        # If batfish key exists and is a string, convert to dict with name
        if 'batfish' in config and isinstance(config['batfish'], str):
            config['batfish'] = {'name': config['batfish']}

        # If batfish section exists and has name, process it
        batfish_config = config.get('batfish', {})
        if isinstance(batfish_config, dict):
            batfish_name = batfish_config.get('name')

            if batfish_name:
                # User provided a batfish name, look it up
                try:
                    batfish_settings = get_object_or_404(BatfishServiceSetting, name=batfish_name)
                except Exception as e:
                    raise ValidationError(f"Invalid batfish setting name '{batfish_name}': {str(e)}")
            else:
                # No name provided, use first available
                batfish_settings = BatfishServiceSetting.objects.first()
                if not batfish_settings:
                    raise ValidationError("No BatfishServiceSetting found in database")

            # Build config with only non-null values
            expanded_batfish = {}

            # Check for conflicts before adding each field
            for field, model_value in [
                ('address', batfish_settings.address),
                ('port_v1', batfish_settings.port_v1),
                ('port_v2', batfish_settings.port_v2),
                ('use_ssl', batfish_settings.use_ssl)
            ]:
                # Only process if the model has a value
                if model_value is not None:
                    # Check if field already exists in user-provided config
                    if field in batfish_config:
                        # User already has this field, don't overwrite
                        continue
                    # Add to expanded config
                    expanded_batfish[field] = model_value

            # Handle network_name - honor if provided, otherwise generate
            if 'network_name' not in batfish_config:
                # Generate dynamically from site code
                expanded_batfish['network_name'] = f"BF_NETWORK_{self.site_code.upper()}"
            
            # Handle snapshot_name - honor if provided, otherwise generate random
            if 'snapshot_name' not in batfish_config:
                # Generate with random string
                random_string = get_random_string(length=8)
                expanded_batfish['snapshot_name'] = f"BF_SNAPSHOT_{random_string}"
                
            # Update batfish config with expanded values
            batfish_config.update(expanded_batfish)
            config['batfish'] = batfish_config
        elif 'batfish' in config:
            # Batfish is present but not a dict or string - replace with default
            config['batfish'] = self._get_default_batfish_config()

    def _get_default_batfish_config(self) -> dict[str, Any]:
        """
        Get default batfish configuration using first available setting.
        Dynamically generates network and snapshot names.
        """
        batfish_settings = BatfishServiceSetting.objects.first()
        if not batfish_settings:
            raise ValidationError("No BatfishServiceSetting found in database")

        # Build config with only non-null values
        config = {}

        if batfish_settings.address is not None:
            config["address"] = batfish_settings.address

        if batfish_settings.port_v1 is not None:
            config["port_v1"] = batfish_settings.port_v1

        if batfish_settings.port_v2 is not None:
            config["port_v2"] = batfish_settings.port_v2

        if batfish_settings.use_ssl is not None:
            config["use_ssl"] = batfish_settings.use_ssl

        # Always generate network_name from site code
        config["network_name"] = f"BF_NETWORK_{self.site_code.upper()}"
        
        # Always generate random snapshot_name
        random_string = get_random_string(length=8)
        config["snapshot_name"] = f"BF_SNAPSHOT_{random_string}"

        return config