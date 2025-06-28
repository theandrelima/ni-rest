from django.urls import path
from . import views

urlpatterns = [
    # Single job execution endpoint - mode determined by JSON payload
    path('execute/', views.NetworkImporterExecuteView.as_view(), name='ni-execute'),
    
    # Job management endpoints
    path('jobs/', views.JobListView.as_view(), name='job-list'),
    path('jobs/<uuid:job_id>/', views.JobDetailView.as_view(), name='job-detail'),
    path('jobs/<uuid:job_id>/logs/', views.JobLogsView.as_view(), name='job-logs'),
]