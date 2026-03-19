import os
import datetime
from django.conf import settings
from django.utils import timezone
from django.shortcuts import redirect
from django.urls import reverse
from django.core.cache import cache

def get_latest_docs_date():
    latest_time = cache.get('latest_terms_mtime')
    
    if latest_time is None:
        paths_to_check = [
            os.path.join(settings.BASE_DIR, 'static', 'docs', 'Informativa WebAPP_revDPO.pdf'),
            os.path.join(settings.BASE_DIR, 'static', 'docs', 'Terms_of_use_CG.pdf'),
            os.path.join(settings.STATIC_ROOT, 'docs', 'Informativa WebAPP_revDPO.pdf'),
            os.path.join(settings.STATIC_ROOT, 'docs', 'Terms_of_use_CG.pdf'),
        ]
        
        timestamps = []
        for f in paths_to_check:
            if os.path.exists(f):
                timestamps.append(os.path.getmtime(f))
        
        if timestamps:
            max_ts = max(timestamps)
            latest_time = datetime.datetime.fromtimestamp(max_ts, tz=datetime.timezone.utc)
        else:
            latest_time = timezone.now() - datetime.timedelta(days=3650)
            
        cache.set('latest_terms_mtime', latest_time, 5) 
        
    return latest_time


class TermsAcceptanceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            if request.user.terms_accepted and request.user.terms_accepted_at:
                latest_doc_date = get_latest_docs_date()
                
                if latest_doc_date > request.user.terms_accepted_at:
                    request.user.terms_accepted = False
                    request.user.save(update_fields=['terms_accepted'])

            if not request.user.terms_accepted:
                allowed_paths = [reverse('accept_terms'), reverse('logout')]

                if request.path not in allowed_paths and not request.path.startswith('/static/'):
                    url = f"{reverse('accept_terms')}?next={request.path}"
                    return redirect(url)

        return self.get_response(request)