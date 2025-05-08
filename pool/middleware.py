import time
from django.shortcuts import render
from django.utils.deprecation import MiddlewareMixin


class RequestThrottleMiddleware(MiddlewareMixin):
    """
    Simple middleware to limit requests to sensitive views to prevent brute forcing.
    This is a lightweight alternative to dedicated rate limiting packages.
    """
    # Views that should be protected
    PROTECTED_PATHS = [
        '/pool/pool/',         # pool_detail view
        '/pool/entry/',        # entry_detail and make_pick views
        '/pool/pool/',         # quick_pick view (starts with this path)
        '/pool/standings/',    # standings view
        '/pool/week/',         # week_picks view
    ]
    
    # How many requests allowed in the time window (per path group)
    REQUEST_LIMIT = 30
    # Time window in seconds (1 minute)
    TIME_WINDOW = 60
    
    def process_request(self, request):
        """Process each request and check if it should be throttled."""
        # Skip throttling for non-protected paths
        path = request.path
        
        # Skip if not a protected path
        if not any(path.startswith(protected) for protected in self.PROTECTED_PATHS):
            return None
            
        # Get or create requests history in session
        if 'request_history' not in request.session:
            request.session['request_history'] = {}
            
        history = request.session['request_history']
        now = time.time()
        
        # Group similar paths together (e.g., all entry paths)
        path_group = next((p for p in self.PROTECTED_PATHS if path.startswith(p)), path)
        
        # Initialize history for this path group if needed
        if path_group not in history:
            history[path_group] = []
            
        # Remove old requests outside the time window
        history[path_group] = [t for t in history[path_group] if now - t < self.TIME_WINDOW]
        
        # Check if limit exceeded
        if len(history[path_group]) >= self.REQUEST_LIMIT:
            # Calculate when throttling will expire
            oldest_timestamp = history[path_group][0]
            reset_time = int(oldest_timestamp + self.TIME_WINDOW - now)
            
            # Create context for template
            context = {
                'title': 'Too Many Requests',
                'message': 'For security reasons, we\'ve temporarily limited access to this page.',
                'wait_time': f'{reset_time} seconds' if reset_time > 0 else 'a few seconds'
            }
            
            # Render the throttle template
            response = render(request, 'pool/rate_limit.html', context)
            response.status_code = 429  # Too Many Requests
            return response
            
        # Add current request timestamp to history
        history[path_group].append(now)
        # Save updated history to session
        request.session.modified = True
        
        # Allow the request to proceed
        return None
