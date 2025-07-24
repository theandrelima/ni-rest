from django.urls import path
from . import views

app_name = 'dashboard'  # Changed from 'gui' to 'dashboard'

urlpatterns = [
    path('', views.home, name='home'),
    path('jobs/', views.JobListView.as_view(), name='job_list'),
    path('jobs/<uuid:job_id>/', views.JobDetailView.as_view(), name='job_detail'),
    path('execute/', views.execute_job, name='execute_job'),
]