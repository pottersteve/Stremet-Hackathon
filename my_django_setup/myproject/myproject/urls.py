from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("customer/", include("customer.urls")),
    path("designer/", include("designer.urls")),
    path("manufacturer/", include("manufacturer.urls")),
    path("warehouse/", include("warehouse.urls")),
    path("", include("home.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
