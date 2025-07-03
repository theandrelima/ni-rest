from django.db import models
from django.contrib.auth.models import User
import uuid
import os
from django.core.exceptions import ValidationError


class NetworkImporterJob(models.Model):
    JOB_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('queued', 'Queued'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    MODE_CHOICES = [
        ('apply', 'Apply'),
        ('check', 'Check'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site_code = models.CharField(max_length=50)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    mode = models.CharField(max_length=10, choices=MODE_CHOICES)
    status = models.CharField(max_length=20, choices=JOB_STATUS_CHOICES, default='pending')
    config_data = models.JSONField()
    celery_task_id = models.CharField(max_length=255, blank=True, null=True, help_text="Celery task ID for tracking")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['site_code', '-created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['celery_task_id']),
        ]
    
    @property
    def success(self) -> bool:
        """Job succeeded if status is completed"""
        return self.status == 'completed'
    
    @property
    def has_errors(self) -> bool:
        """Check if job has any error-level logs"""
        return self.logs.filter(level__in=['ERROR', 'CRITICAL']).exists()
    
    def __str__(self) -> str:
        return f"{self.mode} job for {self.site_code} - {self.status}"

class JobLog(models.Model):
    LOG_LEVEL_CHOICES = [
        ('DEBUG', 'Debug'),
        ('INFO', 'Info'),
        ('WARNING', 'Warning'),
        ('ERROR', 'Error'),
        ('CRITICAL', 'Critical'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(NetworkImporterJob, on_delete=models.CASCADE, related_name='logs')
    timestamp = models.DateTimeField(auto_now_add=True)
    level = models.CharField(max_length=10, choices=LOG_LEVEL_CHOICES)
    message = models.TextField()
    source = models.CharField(max_length=100, blank=True)  # e.g., 'network-importer', 'api'
    
    class Meta:
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['job', 'timestamp']),
            models.Index(fields=['level']),
        ]
    
    def __str__(self) -> str:
        return f"{self.level}: {self.message[:50]}..."
    

class NetworkImporterInventorySettings(models.Model):
    """
    Network Importer Inventory Settings model.
    
    Stores inventory connection settings with token retrieved from environment variables.
    The token is retrieved from env var: NI_INVENTORY_SETTING_TOKEN_<name>
    """
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Unique identifier for this inventory setting"
    )
    address = models.URLField(
        help_text="Base URL for the inventory system (e.g., https://nautobot.example.com)"
    )
    verify_ssl = models.BooleanField(
        default=True,
        help_text="Whether to verify SSL certificates"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Network Importer Inventory Setting"
        verbose_name_plural = "Network Importer Inventory Settings"
    
    def __str__(self) -> str:
        return f"Inventory Settings: {self.name}"
    
    @property
    def token(self) -> str:
        """
        Retrieve token from environment variable.
        
        Returns:
            Token value from environment variable
            
        Raises:
            ValidationError: If environment variable is not set
        """
        env_var_name = f"NI_INVENTORY_SETTING_TOKEN_{self.name}"
        token = os.getenv(env_var_name)
        
        if not token:
            raise ValidationError(
                f"Environment variable '{env_var_name}' is not set or empty. "
                f"Please set this variable with the inventory token for '{self.name}'."
            )
        
        return token
    
    def clean(self) -> None:
        """Validate that the required environment variable exists"""
        super().clean()
        try:
            # This will raise ValidationError if env var is not set
            _ = self.token
        except ValidationError:
            # Re-raise with field-specific error
            raise ValidationError({
                'name': f"Environment variable 'NI_INVENTORY_SETTING_TOKEN_{self.name}' must be set"
            })


class NetworkImporterNetCreds(models.Model):
    """
    Network Importer Network Credentials model.
    
    Stores network credential references with login/password retrieved from environment variables.
    Login is retrieved from: NI_NET_CREDS_LOGIN_<name>
    Password is retrieved from: NI_NET_CREDS_PASSWORD_<name>
    """
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Unique identifier for this network credential set"
    )
    description = models.TextField(
        blank=True,
        help_text="Optional description for this credential set"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Network Importer Network Credential"
        verbose_name_plural = "Network Importer Network Credentials"
    
    def __str__(self) -> str:
        return f"Network Creds: {self.name}"
    
    @property
    def login(self) -> str:
        """
        Retrieve login from environment variable.
        
        Returns:
            Login value from environment variable
            
        Raises:
            ValidationError: If environment variable is not set
        """
        env_var_name = f"NI_NET_CREDS_LOGIN_{self.name}"
        login = os.getenv(env_var_name)
        
        if not login:
            raise ValidationError(
                f"Environment variable '{env_var_name}' is not set or empty. "
                f"Please set this variable with the network login for '{self.name}'."
            )
        
        return login
    
    @property
    def password(self) -> str:
        """
        Retrieve password from environment variable.
        
        Returns:
            Password value from environment variable
            
        Raises:
            ValidationError: If environment variable is not set
        """
        env_var_name = f"NI_NET_CREDS_PASSWORD_{self.name}"
        password = os.getenv(env_var_name)
        
        if not password:
            raise ValidationError(
                f"Environment variable '{env_var_name}' is not set or empty. "
                f"Please set this variable with the network password for '{self.name}'."
            )
        
        return password
    
    def clean(self) -> None:
        """Validate that the required environment variables exist"""
        super().clean()
        errors = {}
        
        try:
            _ = self.login
        except ValidationError:
            errors['name'] = f"Environment variable 'NI_NET_CREDS_LOGIN_{self.name}' must be set"
        
        try:
            _ = self.password
        except ValidationError:
            if 'name' in errors:
                errors['name'] += f" and 'NI_NET_CREDS_PASSWORD_{self.name}' must be set"
            else:
                errors['name'] = f"Environment variable 'NI_NET_CREDS_PASSWORD_{self.name}' must be set"
        
        if errors:
            raise ValidationError(errors)


class BatfishServiceSetting(models.Model):
    """
    Batfish Service Settings model.
    
    Stores Batfish service configuration. All fields except name are optional
    since network-importer has built-in logic to handle defaults and env var overrides.
    """
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Unique identifier for this Batfish service setting"
    )
    address = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Batfish service address (optional)"
    )
    network_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Batfish network name (optional)"
    )
    snapshot_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Batfish snapshot name (optional)"
    )
    port_v1 = models.IntegerField(
        blank=True,
        null=True,
        help_text="Batfish API v1 port (optional)"
    )
    port_v2 = models.IntegerField(
        blank=True,
        null=True,
        help_text="Batfish API v2 port (optional)"
    )
    use_ssl = models.BooleanField(
        blank=True,
        null=True,
        help_text="Whether to use SSL (optional)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Batfish Service Setting"
        verbose_name_plural = "Batfish Service Settings"
    
    def __str__(self) -> str:
        return f"Batfish Service: {self.name}"
    
    def clean(self) -> None:
        """Validate port ranges if they are provided"""
        super().clean()
        errors = {}
        
        if self.port_v1 is not None and not (1024 <= self.port_v1 <= 65535):
            errors['port_v1'] = "Port must be between 1024 and 65535"
        
        if self.port_v2 is not None and not (1024 <= self.port_v2 <= 65535):
            errors['port_v2'] = "Port must be between 1024 and 65535"
        
        if (self.port_v1 is not None and self.port_v2 is not None and 
            self.port_v1 == self.port_v2):
            errors['port_v2'] = "Port v2 must be different from port v1"
        
        if errors:
            raise ValidationError(errors)