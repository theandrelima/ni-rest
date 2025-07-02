from rest_framework import serializers
from .models import NetworkImporterJob, JobLog

class NetworkImporterExecuteSerializer(serializers.Serializer):
    site = serializers.CharField(max_length=50, required=True, help_text="Site code/identifier")
    mode = serializers.ChoiceField(choices=['apply', 'check'], required=True, help_text="Execution mode: apply or check")
    settings = serializers.DictField(required=True, help_text="Network importer configuration settings")
    
    def validate_site(self, value: str) -> str:
        """Validate site code format"""
        if not value or not value.strip():
            raise serializers.ValidationError("Site code cannot be empty")
        return value.strip()
    
    def validate_settings(self, value: dict) -> dict:
        """Validate settings structure and required nested fields"""
        # Validate inventory section
        if 'inventory' not in value:
            raise serializers.ValidationError("settings.inventory is required")
        
        inventory = value['inventory']
        if 'name' not in inventory:
            raise serializers.ValidationError("settings.inventory.name is required")
        
        # Validate network section
        if 'network' not in value:
            raise serializers.ValidationError("settings.network is required")
        
        network = value['network']
        if 'credentials_name' not in network:
            raise serializers.ValidationError("settings.network.credentials_name is required")
        
        return value

class JobSerializer(serializers.ModelSerializer):
    success = serializers.ReadOnlyField()
    has_errors = serializers.ReadOnlyField()
    logs_count = serializers.SerializerMethodField()
    error_logs_count = serializers.SerializerMethodField()
    
    class Meta:
        model = NetworkImporterJob
        fields = [
            'id', 'site_code', 'mode', 'status', 'success', 'has_errors',
            'created_at', 'started_at', 'completed_at', 'celery_task_id',
            'logs_count', 'error_logs_count'
        ]
    
    def get_logs_count(self, obj: NetworkImporterJob) -> int:
        return obj.logs.count()
    
    def get_error_logs_count(self, obj: NetworkImporterJob) -> int:
        return obj.logs.filter(level__in=['ERROR', 'CRITICAL']).count()

class JobLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobLog
        fields = ['id', 'timestamp', 'level', 'message', 'source']