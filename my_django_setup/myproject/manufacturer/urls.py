from django.urls import path
from . import views

urlpatterns = [
    # The main dashboard (your 3-panel screen)
    path('', views.dashboard, name='manufacturer_dashboard'), 
    
    # The three specific panels
    path('admin-panel/', views.admin_panel, name='admin_panel'),
    path('customer-panel/', views.customer_panel, name='customer_panel'),
    path('production-panel/', views.manufacturer_panel, name='manufacturer_panel'),
]