from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

def root_redirect(request):
    """Redirect root URL to dashboard home page - REQUIRES LOGIN"""
    if not request.user.is_authenticated:
        return redirect('login')
    return redirect('dashboard:home')

urlpatterns = [
    path('', root_redirect),
    path('admin/', admin.site.urls),
    path('api/', include('ni_rest.api.urls')),

    # Dashboard app URLs (formerly gui) - ALL REQUIRE LOGIN
    path('dashboard/', include('ni_rest.gui.urls')),

    # Authentication URLs
    path('login/', auth_views.LoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(
        template_name='registration/logged_out.html',
        http_method_names=['post'],
        next_page='logged_out'
    ), name='logout'),
    path('logged-out/', auth_views.TemplateView.as_view(
        template_name='registration/logged_out.html'
    ), name='logged_out'),
    
    # OpenAPI schema and documentation - REQUIRE LOGIN WITH REDIRECT
    path('api/schema/', login_required(SpectacularAPIView.as_view(), login_url='login'), name='schema'),
    path('api/docs/', login_required(SpectacularSwaggerView.as_view(url_name='schema'), login_url='login'), name='swagger-ui'),
    path('api/redoc/', login_required(SpectacularRedocView.as_view(url_name='schema'), login_url='login'), name='redoc'),
]