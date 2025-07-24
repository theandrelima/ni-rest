from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, DetailView
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta
import json

from ..api.models import NetworkImporterJob, JobLog
from ..api.models import NetworkImporterInventorySettings, NetworkImporterNetCreds, BatfishServiceSetting
from .forms import ExecuteJobForm


@login_required(login_url='login')
def home(request):
    """Dashboard with overview and recent jobs - REQUIRES LOGIN"""
    # Get recent jobs
    recent_jobs = NetworkImporterJob.objects.all().order_by('-created_at')[:10]
    
    # Calculate statistics
    total_jobs = NetworkImporterJob.objects.count()
    completed_jobs = NetworkImporterJob.objects.filter(status='completed').count()
    failed_jobs = NetworkImporterJob.objects.filter(status='failed').count()
    running_jobs = NetworkImporterJob.objects.filter(status__in=['running', 'queued']).count()
    
    # Jobs from last 24 hours
    last_24h = timezone.now() - timedelta(hours=24)
    recent_jobs_count = NetworkImporterJob.objects.filter(created_at__gte=last_24h).count()
    
    context = {
        'recent_jobs': recent_jobs,
        'stats': {
            'total': total_jobs,
            'completed': completed_jobs,
            'failed': failed_jobs,
            'running': running_jobs,
            'recent_24h': recent_jobs_count,
        }
    }
    return render(request, 'gui/home.html', context)


class JobListView(LoginRequiredMixin, ListView):
    """List all jobs with filtering and pagination - REQUIRES LOGIN"""
    model = NetworkImporterJob
    template_name = 'gui/job_list.html'
    context_object_name = 'jobs'
    paginate_by = 20
    login_url = 'login'
    
    def get_queryset(self):
        queryset = NetworkImporterJob.objects.all().order_by('-created_at')
        
        # Apply filters from query params
        site_filter = self.request.GET.get('site_code')
        status_filter = self.request.GET.get('status')
        mode_filter = self.request.GET.get('mode')
        
        if site_filter:
            queryset = queryset.filter(site_code__icontains=site_filter)
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
            
        if mode_filter:
            queryset = queryset.filter(mode=mode_filter)
            
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = NetworkImporterJob.JOB_STATUS_CHOICES
        context['mode_choices'] = NetworkImporterJob.MODE_CHOICES
        return context


class JobDetailView(LoginRequiredMixin, ListView):
    """Job detail view with logs - REQUIRES LOGIN"""
    template_name = 'gui/job_detail.html'
    context_object_name = 'logs'
    paginate_by = 100
    login_url = 'login'
    
    def get_queryset(self):
        self.job = get_object_or_404(NetworkImporterJob, id=self.kwargs['job_id'])
        logs = self.job.logs.all().order_by('timestamp')
        
        # Filter by log level if specified
        level_filter = self.request.GET.get('level')
        if level_filter:
            logs = logs.filter(level=level_filter)
            
        return logs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['job'] = self.job
        return context


@login_required(login_url='login')
def execute_job(request):
    """Execute a new job - REQUIRES LOGIN"""
    if request.method == 'POST':
        form = ExecuteJobForm(request.POST)
        if form.is_valid():
            site_code = form.cleaned_data['site_code']
            # Convert dry_run checkbox to mode value
            dry_run = form.cleaned_data['dry_run']
            mode = 'check' if dry_run else 'apply'
            
            inventory_settings = form.cleaned_data['inventory_settings']
            network_credentials = form.cleaned_data['network_credentials']
            batfish_settings = form.cleaned_data['batfish_settings']
            
            # Build settings dictionary
            settings = {
                'inventory': {
                    'name': inventory_settings.name
                },
                'network': {
                    'credentials_name': network_credentials.name
                }
            }
            
            # Add batfish settings if provided
            if batfish_settings:
                settings['batfish'] = batfish_settings.name
                
            # Create job record
            job = NetworkImporterJob.objects.create(
                site_code=site_code,
                user=request.user,
                mode=mode,
                config_data=settings,
                status='pending'
            )
            
            # Import here to avoid circular imports
            from ..api.services.config_generator import NetworkImporterConfigGenerator
            from ..api.services.ni_service import NetworkImporterService
            from ..api.tasks import execute_network_import_task
            from ..api.utils import CeleryWorkerManager
            
            # Check if workers are available
            if CeleryWorkerManager.has_workers():
                # Queue job to worker
                task = execute_network_import_task.delay(str(job.id), check=(mode == 'check'))
                job.celery_task_id = task.id
                job.status = 'queued'
                job.save()
                messages.success(request, f"Job queued for execution (Job ID: {job.id})")
            else:
                # Execute job immediately
                job.status = 'running'
                job.started_at = timezone.now()
                job.save()
                
                try:
                    # Execute directly
                    config_gen = NetworkImporterConfigGenerator(job.site_code)
                    config_dict = config_gen.generate_config_dict(job.config_data)
                    service = NetworkImporterService(job, config_dict)
                    service.run(check=(mode == 'check'))
                    messages.success(request, f"Job executed successfully (Job ID: {job.id})")
                except Exception as e:
                    messages.error(request, f"Error executing job: {str(e)}")
            
            return redirect('dashboard:job_detail', job_id=job.id)
    else:
        form = ExecuteJobForm()
    
    return render(request, 'gui/execute_job.html', {'form': form})