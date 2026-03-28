from django.urls import path
from . import views

urlpatterns = [
    # The base URL for this app will be handled by the main project urls.py
    path('', views.customer_panel, name='customer_panel'),
]