from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls), 
    
    # 1. Route customer traffic to the Customer app
    path('customer/', include('customer.urls')), 
    
    # 2. Route everything else (dashboard, staff logins) to the Home app
    path('', include('home.urls')), 
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)