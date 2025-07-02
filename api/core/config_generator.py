from typing import Any
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from network_importer.config import DEFAULT_DRIVERS_MAPPING
from ..models import (
    NetworkImporterInventorySettings,
    NetworkImporterNetCreds,
    BatfishServiceSetting
)

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
        
        # Base configuration structure - NO LOGS SECTION!
        config = {
            "main": self._get_main_config(config_data.get("main", {})),
            "inventory": self._get_inventory_config(config_data.get("inventory", {})),
            "network": self._get_network_config(config_data.get("network", {})),
            "batfish": self._get_batfish_config_internal(config_data.get("batfish")),
            "drivers": self._get_drivers_config(config_data.get("drivers", {})),
        }
        
        # Add optional user-configurable sections if provided
        if "adapters" in config_data:
            config["adapters"] = self._get_adapters_config(config_data["adapters"])
        
        return config
    
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
                          Must contain 'name' referencing a NetworkImporterInventorySettings
            
        Returns:
            Dictionary with inventory configuration and resolved credentials
            
        Raises:
            ValidationError: If name is missing or invalid
        """
        config = {}
        
        # Handle supported platforms
        if "supported_platforms" in inventory_data:
            config["supported_platforms"] = inventory_data["supported_platforms"]
        else:
            config["supported_platforms"] = ["cisco_ios", "cisco_asa", "cisco_nxos", "juniper_junos", "arista_eos"]
        
        # Get settings from model
        inventory_name = inventory_data.get("name")
        if not inventory_name:
            raise ValidationError("inventory.name is required")
        
        try:
            inventory_settings = get_object_or_404(NetworkImporterInventorySettings, name=inventory_name)
        except Exception as e:
            raise ValidationError(f"Invalid inventory name '{inventory_name}': {str(e)}")
        
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
            raise ValidationError(f"Error accessing inventory settings for '{inventory_name}': {str(e)}")
        
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
            }
        
        return config
    
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
                batfish_settings = get_object_or_404(BatfishServiceSetting, name=batfish_setting_name)
            else:
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
        
        config["mapping"] = DEFAULT_DRIVERS_MAPPING.copy()
        
        if "mapping" in drivers_data:
            config["mapping"].update(drivers_data["mapping"])
        
        return config