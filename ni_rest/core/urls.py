from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

def root_redirect(request):
    """Redirect root URL to API"""
    return redirect('/api/')

urlpatterns = [
    path('', root_redirect),
    path('admin/', admin.site.urls),
    path('api/', include('ni_rest.api.urls')),
    
    # OpenAPI schema and documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]