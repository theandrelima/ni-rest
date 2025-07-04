from django.contrib import admin
from rest_framework.authtoken.models import Token
from .models import (
    NetworkImporterJob, 
    JobLog,
    NetworkImporterInventorySettings,
    NetworkImporterNetCreds,
    BatfishServiceSetting
)

# Job Management (Read-only for monitoring)
@admin.register(NetworkImporterJob)
class NetworkImporterJobAdmin(admin.ModelAdmin):
    list_display = ['site_code', 'mode', 'status', 'user', 'created_at', 'success']
    list_filter = ['status', 'mode', 'created_at']
    search_fields = ['site_code', 'user__username']
    readonly_fields = ['id', 'site_code', 'mode', 'status', 'user', 'success', 'has_errors',
                      'created_at', 'started_at', 'completed_at', 'config_data']
    
    def has_add_permission(self, request):
        return False  # Can't create jobs via admin - use API
    
    def has_change_permission(self, request, obj=None):
        return False  # Can't edit jobs via admin - read-only
    
    def has_delete_permission(self, request, obj=None):
        return True   # Allow deletion for cleanup

# Job Logs (Read-only for monitoring)
@admin.register(JobLog)
class JobLogAdmin(admin.ModelAdmin):
    list_display = ['job', 'level', 'timestamp', 'message']
    list_filter = ['level', 'timestamp']
    search_fields = ['message', 'job__site_code']
    readonly_fields = ['job', 'level', 'timestamp', 'message', 'source']
    
    def has_add_permission(self, request):
        return False  # Can't create logs via admin - auto-generated
    
    def has_change_permission(self, request, obj=None):
        return False  # Can't edit logs via admin - read-only
    
    def has_delete_permission(self, request, obj=None):
        return True   # Allow deletion for cleanup

# Configuration Models (Editable)
@admin.register(NetworkImporterInventorySettings)
class NetworkImporterInventorySettingsAdmin(admin.ModelAdmin):
    list_display = ['name', 'address', 'verify_ssl', 'created_at']
    search_fields = ['name', 'address']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(NetworkImporterNetCreds)
class NetworkImporterNetCredsAdmin(admin.ModelAdmin):
    list_display = ['name', 'description', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(BatfishServiceSetting)
class BatfishServiceSettingAdmin(admin.ModelAdmin):
    list_display = ['name', 'address', 'network_name', 'created_at']
    search_fields = ['name', 'address', 'network_name']
    readonly_fields = ['created_at', 'updated_at']

# Fix Token duplication - check if already registered and unregister
try:
    admin.site.unregister(Token)
except admin.sites.NotRegistered:
    pass  # Token wasn't registered, that's fine

