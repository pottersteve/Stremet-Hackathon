from django.urls import path

from . import views

urlpatterns = [
    path("", views.warehouse_dashboard, name="warehouse_dashboard"),
    path("store/", views.warehouse_store, name="warehouse_store"),
    path("pickup/", views.warehouse_pickup_queue, name="warehouse_pickup_queue"),
    path("receive/", views.warehouse_receive, name="warehouse_receive"),
    path(
        "plan/<int:plan_id>/pickup/<int:step_id>/",
        views.warehouse_pickup_detail,
        name="warehouse_pickup_detail",
    ),
    path(
        "reservations/new/",
        views.warehouse_reservation_create,
        name="warehouse_reservation_create",
    ),
    path("inventory/", views.warehouse_inventory, name="warehouse_inventory"),
]
