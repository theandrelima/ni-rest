from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, filters

from .models import NetworkImporterJob, JobLog
from .serializers import NetworkImporterExecuteSerializer, JobSerializer, JobLogSerializer
from .core.config_generator import NetworkImporterConfigGenerator
from .core.ni_service import NetworkImporterService

class NetworkImporterExecuteView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Execute network-importer with site and mode from JSON payload"""
        
        serializer = NetworkImporterExecuteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        validated_data = serializer.validated_data
        site_code = validated_data['site']
        mode = validated_data['mode']
        settings = validated_data['settings']
        
        # Create job record - NO command_executed!
        job = NetworkImporterJob.objects.create(
            site_code=site_code,
            user=request.user,
            mode=mode,
            config_data=settings
        )
        
        try:
            # Generate config dictionary
            config_gen = NetworkImporterConfigGenerator(site_code)
            config_dict = config_gen.generate_config_dict(settings)
            
            # Execute with direct Python integration
            service = NetworkImporterService(job, config_dict)
            check_mode = (mode == 'check')
            result = service.run(check=check_mode)
            
            # Return job details with current status
            job.refresh_from_db()
            job_serializer = JobSerializer(job)
            
            return Response({
                'job': job_serializer.data,
                'execution_result': result
            }, status=status.HTTP_200_OK if job.success else status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            job.status = 'failed'
            job.completed_at = timezone.now()
            job.save()
            
            return Response(
                {
                    'error': 'Internal server error',
                    'details': str(e),
                    'job_id': str(job.id)
                }, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class JobListView(generics.ListAPIView):
    queryset = NetworkImporterJob.objects.all()
    serializer_class = JobSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['site_code', 'mode', 'status']
    ordering_fields = ['created_at', 'started_at', 'completed_at']
    ordering = ['-created_at']

class JobDetailView(generics.RetrieveAPIView):
    queryset = NetworkImporterJob.objects.all()
    serializer_class = JobSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'
    lookup_url_kwarg = 'job_id'

class JobLogsView(generics.ListAPIView):
    serializer_class = JobLogSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['level']
    ordering_fields = ['timestamp']
    ordering = ['timestamp']
    
    def get_queryset(self):
        job_id = self.kwargs['job_id']
        return JobLog.objects.filter(job_id=job_id)