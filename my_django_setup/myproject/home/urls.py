from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="home_dashboard"),
    path("admin_panel/", views.admin_panel, name="admin_panel"),
    path("request-quote/", views.customer_request_quote, name="customer_request_quote"),
    path("login/", views.staff_login, name="login"),
    path("logout/", views.staff_logout, name="logout"),
    path("dashboard/", views.staff_dashboard, name="staff_dashboard"),
    path("update-status/", views.update_item_status, name="update_item_status"),
    path("support/", views.support_hub, name="support_hub"),
    path("send-chat/", views.send_chat_message, name="send_chat_message"),
    path("ai-suggest/", views.generate_ai_suggestion, name="generate_ai_suggestion"),
    path("client_directory/", views.client_directory, name="client_directory"),
]
