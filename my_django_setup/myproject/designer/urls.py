from django.urls import path

from . import views

urlpatterns = [
    path("", views.designer_dashboard, name="designer_dashboard"),
    path("order/<int:order_id>/", views.order_detail, name="designer_order_detail"),
    path("plan/<int:plan_id>/", views.plan_editor, name="designer_plan_editor"),
    path("plan/<int:plan_id>/step/add/", views.add_step, name="designer_add_step"),
    path(
        "plan/<int:plan_id>/step/<int:step_id>/",
        views.step_detail,
        name="designer_step_detail",
    ),
    path(
        "plan/<int:plan_id>/step/<int:step_id>/delete/",
        views.delete_step,
        name="designer_delete_step",
    ),
    path(
        "plan/<int:plan_id>/graph-data/", views.graph_data, name="designer_graph_data"
    ),
    path(
        "plan/<int:plan_id>/save-graph/", views.save_graph, name="designer_save_graph"
    ),
]
