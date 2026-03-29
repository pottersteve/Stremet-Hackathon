from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from .models import (
    ChatMessage,
    Client,
    Order,
    OrderImage,
    OrderModificationRequest,
    UserProfile,
)


class OrderImageInline(admin.TabularInline):
    model = OrderImage
    extra = 1


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_id",
        "client",
        "steel_grade",
        "status",
        "quantity_tons",
        "target_delivery",
    )
    list_filter = ("status", "steel_grade", "heat_treatment")
    search_fields = ("order_id", "client__company_name")
    inlines = [OrderImageInline]


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("company_name", "name", "email")
    search_fields = ("company_name", "email")


@admin.register(OrderModificationRequest)
class OrderModificationRequestAdmin(admin.ModelAdmin):
    list_display = ("order", "is_approved", "created_at")
    list_filter = ("is_approved",)


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("order", "sender", "timestamp")


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role")
    list_filter = ("role",)


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = "Role"


class UserAdmin(BaseUserAdmin):
    inlines = [UserProfileInline]


admin.site.unregister(User)
admin.site.register(User, UserAdmin)
