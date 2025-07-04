from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, filters
from celery.result import AsyncResult
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes

from .models import NetworkImporterJob, JobLog
from .serializers import NetworkImporterExecuteSerializer, JobSerializer, JobLogSerializer
from .tasks import execute_network_import_task
from .utils import CeleryWorkerManager

@extend_schema(
    operation_id='api_root',
    summary='API Root',
    description='Get API information and available endpoints with worker status',
    responses={200: {
        'type': 'object',
        'properties': {
            'endpoints': {
                'type': 'object',
                'description': 'Available API endpoints'
            },
            'worker_status': {
                'type': 'object',
                'description': 'Celery worker availability status'
            }
        }
    }}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_root(request):
    """Simple API root endpoint with known API endpoints."""
    
    # Get the API URL patterns specifically
    from ni_rest.api.urls import urlpatterns
    from django.urls.resolvers import URLPattern
    
    endpoints = {}
    
    for pattern in urlpatterns:
        if isinstance(pattern, URLPattern) and pattern.name:
            # Get the pattern string
            pattern_str = str(pattern.pattern)
            
            # Clean it up
            clean_pattern = pattern_str.replace('^', '').replace('$', '')
            
            # Skip endpoints that require parameters
            if '<' in clean_pattern and '>' in clean_pattern:
                continue  # Skip parameterized endpoints
            
            # Build URL
            full_url = request.build_absolute_uri('/api/' + clean_pattern)
            endpoints[pattern.name] = full_url
    
    return Response({
        'endpoints': endpoints,
        'worker_status': {
            'workers_available': CeleryWorkerManager.has_workers(),
            'worker_count': CeleryWorkerManager.get_worker_count(),
            'execution_mode': 'async' if CeleryWorkerManager.has_workers() else 'immediate'
        }
    })

@extend_schema(
    operation_id='execute_network_import',
    summary='Execute Network Import',
    description='''
    Execute a network import operation for a specific site.
    
    The operation will be queued to Celery workers if available,
    or executed immediately if no workers are present.
    
    Supports both 'check' mode (dry run) and 'apply' mode (make changes).
    ''',
    examples=[
        OpenApiExample(
            'Apply Mode Example',
            summary='Execute changes on lab01 site',
            description='Execute network import with changes applied',
            value={
                "site": "lab01",
                "mode": "apply",
                "settings": {
                    "inventory": {"name": "nautobot_dev"},
                    "network": {"credentials_name": "lab_devices"}
                }
            }
        ),
        OpenApiExample(
            'Check Mode Example',
            summary='Dry run on production site',
            description='Check what changes would be made without applying them',
            value={
                "site": "prod01",
                "mode": "check", 
                "settings": {
                    "inventory": {"name": "nautobot_prod"},
                    "network": {"credentials_name": "prod_routers"}
                }
            }
        )
    ]
)
class NetworkImporterExecuteView(APIView):
    """Execute network import operations with automatic worker detection."""
    permission_classes = [IsAuthenticated]
    
    def post(self, request) -> Response:
        """Execute network-importer with graceful worker detection"""
        
        serializer = NetworkImporterExecuteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        validated_data = serializer.validated_data
        site_code = validated_data['site']
        mode = validated_data['mode']
        settings = validated_data['settings']
        
        # Create job record
        job = NetworkImporterJob.objects.create(
            site_code=site_code,
            user=request.user,
            mode=mode,
            config_data=settings,
            status='queued'
        )
        
        # Check worker availability
        worker_count = CeleryWorkerManager.get_worker_count()
        has_workers = worker_count > 0
        
        try:
            check_mode = (mode == 'check')
            
            if has_workers:
                # Workers available - queue normally
                task = execute_network_import_task.delay(str(job.id), check=check_mode)
                job.celery_task_id = task.id
                job.save()
                
                return Response({
                    'job': JobSerializer(job).data,
                    'task_id': task.id,
                    'message': f'Network import {mode} job queued for worker execution',
                    'execution_mode': 'worker',
                    'worker_count': worker_count,
                    'status': 'queued'
                }, status=status.HTTP_202_ACCEPTED)
            
            else:
                # No workers available - execute immediately in current process
                job.status = 'running'
                job.started_at = timezone.now()
                job.save()
                
                # Import here to avoid circular imports
                from .services.config_generator import NetworkImporterConfigGenerator
                from .services.ni_service import NetworkImporterService
                
                # Execute directly
                config_gen = NetworkImporterConfigGenerator(job.site_code)
                config_dict = config_gen.generate_config_dict(job.config_data)
                service = NetworkImporterService(job, config_dict)
                result = service.run(check=check_mode)
                
                # Job status is updated by the service
                job.refresh_from_db()
                
                return Response({
                    'job': JobSerializer(job).data,
                    'result': result,
                    'message': f'Network import {mode} job executed immediately (no workers available)',
                    'execution_mode': 'immediate',
                    'worker_count': 0,
                    'status': job.status
                }, status=status.HTTP_200_OK if result.get('success') else status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        except Exception as e:
            job.status = 'failed'
            job.completed_at = timezone.now()
            job.save()
            
            return Response({
                'error': 'Failed to execute job',
                'details': str(e),
                'job_id': str(job.id),
                'execution_mode': 'worker' if has_workers else 'immediate'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@extend_schema_view(
    get=extend_schema(
        operation_id='list_jobs',
        summary='List Jobs',
        description='List all network import jobs with optional filtering',
        parameters=[
            OpenApiParameter('site_code', OpenApiTypes.STR, description='Filter by site code'),
            OpenApiParameter('mode', OpenApiTypes.STR, description='Filter by execution mode'),
            OpenApiParameter('status', OpenApiTypes.STR, description='Filter by job status'),
            OpenApiParameter('ordering', OpenApiTypes.STR, description='Order by field (prefix with - for desc)'),
        ]
    )
)
class JobListView(generics.ListAPIView):
    """List all network import jobs with filtering and ordering."""
    queryset = NetworkImporterJob.objects.all()
    serializer_class = JobSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['site_code', 'mode', 'status']
    ordering_fields = ['created_at', 'started_at', 'completed_at']
    ordering = ['-created_at']

@extend_schema_view(
    get=extend_schema(
        operation_id='get_job_detail',
        summary='Get Job Details',
        description='Get detailed information about a specific job'
    )
)
class JobDetailView(generics.RetrieveAPIView):
    """Get detailed information about a specific job."""
    queryset = NetworkImporterJob.objects.all()
    serializer_class = JobSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'
    lookup_url_kwarg = 'job_id'

@extend_schema_view(
    get=extend_schema(
        operation_id='list_job_logs',
        summary='Get Job Logs',
        description='Get all logs for a specific job with optional filtering',
        parameters=[
            OpenApiParameter('level', OpenApiTypes.STR, description='Filter by log level'),
            OpenApiParameter('ordering', OpenApiTypes.STR, description='Order by timestamp'),
        ]
    )
)
class JobLogsView(generics.ListAPIView):
    """Get all logs for a specific job."""
    serializer_class = JobLogSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['level']
    ordering_fields = ['timestamp']
    ordering = ['timestamp']
    
    def get_queryset(self):
        job_id = self.kwargs['job_id']
        return JobLog.objects.filter(job_id=job_id)

@extend_schema(
    operation_id='get_job_status',
    summary='Get Job Status',
    description='Get real-time job status including Celery task information',
    responses={200: JobSerializer}
)
class JobStatusView(APIView):
    """Get real-time job status including Celery task state"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, job_id: str) -> Response:
        """Get current job status with Celery task information"""
        
        try:
            job = get_object_or_404(NetworkImporterJob, id=job_id)
            
            # Get Celery task status if available
            celery_state = None
            celery_info = None
            
            if job.celery_task_id:
                task_result = AsyncResult(job.celery_task_id)
                celery_state = task_result.state
                if task_result.info:
                    celery_info = task_result.info
            
            job_serializer = JobSerializer(job)
            response_data = job_serializer.data
            
            # Add Celery information
            response_data.update({
                'celery_task_id': job.celery_task_id,
                'celery_state': celery_state,
                'celery_info': celery_info,
                'worker_count': CeleryWorkerManager.get_worker_count(),
                'has_workers': CeleryWorkerManager.has_workers(),
            })
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )