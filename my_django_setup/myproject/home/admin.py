from django.contrib import admin
from .models import Client, Order, OrderItem, OrderImage, OrderModificationRequest, ChatMessage, UserProfile

class OrderImageInline(admin.TabularInline):
    model = OrderImage
    extra = 1

# --- ADD THIS NEW INLINE FOR ITEMS ---
class OrderItemInline(admin.StackedInline):
    model = OrderItem
    extra = 1

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_id', 'client', 'steel_grade', 'status', 'quantity_tons', 'target_delivery')
    list_filter = ('status', 'steel_grade', 'heat_treatment')
    search_fields = ('order_id', 'client__company_name')
    # Add OrderItemInline to the list below!
    inlines = [OrderItemInline, OrderImageInline] 

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'name', 'email')
    search_fields = ('company_name', 'email')

@admin.register(OrderModificationRequest)
class OrderModificationRequestAdmin(admin.ModelAdmin):
    list_display = ('order', 'is_approved', 'created_at')
    list_filter = ('is_approved',)

@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('order', 'sender', 'timestamp')

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role')
    list_filter = ('role',)