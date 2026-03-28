from django.urls import path

from home.views import customer_panel

urlpatterns = [
    path("", customer_panel, name="customer_panel"),
]
