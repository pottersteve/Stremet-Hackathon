from django.urls import path
from . import views

urlpatterns = [
    path('', views.manufacturer_dashboard, name='manufacturer_dashboard'),
    path('order/<int:order_id>/', views.order_execution, name='manufacturer_order_execution'),
    path('plan/<int:plan_id>/step/<int:step_id>/', views.step_execution, name='manufacturer_step_execution'),
]
