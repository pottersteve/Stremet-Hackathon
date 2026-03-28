from django.urls import path
from . import views

urlpatterns = [
    # Main Landing Page
    path('', views.dashboard, name='home_dashboard'),
    
    # Unified Staff Portal
    path('login/', views.staff_login, name='staff_login'),    
    path('logout/', views.staff_logout, name='staff_logout'),
    path('dashboard/', views.staff_dashboard, name='staff_dashboard'),
    
    # Hidden Javascript Endpoint for the Flowchart
    path('update-status/', views.update_item_status, name='update_item_status'),
]