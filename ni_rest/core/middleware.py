from django.shortcuts import redirect
from django.urls import reverse
from django.http import HttpResponseRedirect
from rest_framework.response import Response
from rest_framework import status


class APIAuthenticationMiddleware:
    """
    Middleware to redirect unauthenticated API requests to login page
    instead of returning 401 errors when accessed via browser.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        # Check if this is an API request that returned 401/403
        if (request.path.startswith('/api/') and 
            response.status_code in [401, 403] and
            not request.user.is_authenticated and
            self._is_browser_request(request)):
            
            # Redirect to login page instead of showing 401
            return HttpResponseRedirect(reverse('login'))
            
        return response
    
    def _is_browser_request(self, request):
        """
        Check if this is a browser request (not an API client)
        based on Accept header.
        """
        accept_header = request.META.get('HTTP_ACCEPT', '')
        return 'text/html' in accept_header and 'application/json' not in accept_header