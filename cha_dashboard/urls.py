from django.contrib import admin
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from django.http import HttpResponse
import os

def serve_sw(request):
    sw_path = os.path.join(settings.BASE_DIR, 'dashboard', 'static', 'dashboard', 'sw.js')
    with open(sw_path, 'r', encoding='utf-8') as f:
        content = f.read()
    # Stamp this deploy's version into the cache name so every deploy gets
    # a fresh service-worker cache automatically — see the STATIC_VERSION
    # comment in settings.py for why this matters (no more hard refreshes).
    content = content.replace('__CACHE_VERSION__', str(settings.STATIC_VERSION))
    response = HttpResponse(content, content_type='application/javascript')
    response['Service-Worker-Allowed'] = '/'
    # Browsers/proxies must not cache sw.js itself, or they'll keep serving
    # an old service worker (with an old cache name baked in) long after a
    # new one has been deployed.
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response

urlpatterns = [
    path('admin/', admin.site.urls),
    path('sw.js', serve_sw, name='service_worker'),
    path('', include('dashboard.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)