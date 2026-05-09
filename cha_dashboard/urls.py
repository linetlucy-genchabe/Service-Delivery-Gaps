from django.contrib import admin
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from django.http import FileResponse
import os

def serve_sw(request):
    sw_path = os.path.join(settings.BASE_DIR, 'dashboard', 'static', 'dashboard', 'sw.js')
    response = FileResponse(open(sw_path, 'rb'), content_type='application/javascript')
    response['Service-Worker-Allowed'] = '/'
    return response

urlpatterns = [
    path('admin/', admin.site.urls),
    path('sw.js', serve_sw, name='service_worker'),
    path('', include('dashboard.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)