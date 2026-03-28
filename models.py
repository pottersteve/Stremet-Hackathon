from django.db import models
from django.contrib.auth.models import User


class Client(models.Model):
    name = models.CharField(max_length=200)
    email = models.EmailField(unique=True)
    company_name = models.CharField(max_length=200)

    def __str__(self):
        return self.company_name

class Order(models.Model):
    # Steel Manufacturing Specific Stages
    STAGE_CHOICES = [
        ('order_received', 'Order Received'),
        ('raw_materials', 'Raw Materials Preparation'),
        ('melting', 'Melting & Refining'),
        ('casting', 'Continuous Casting'),
        ('rolling', 'Hot/Cold Rolling'),
        ('finishing', 'Finishing & Inspection'),
        ('shipping', 'Ready for Shipping'),
        ('delivered', 'Delivered')
    ]

    order_id = models.CharField(max_length=20, unique=True)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='orders')
    
    # Steel Specifications
    steel_grade = models.CharField(max_length=50, help_text="e.g., 304 Stainless, A36 Carbon")
    dimensions = models.CharField(max_length=100, help_text="Thickness x Width x Length")
    quantity_tons = models.DecimalField(max_digits=8, decimal_places=2)
    
    status = models.CharField(max_length=30, choices=STAGE_CHOICES, default='order_received')
    created_at = models.DateTimeField(auto_now_add=True)
    target_delivery = models.DateField()

    def __str__(self):
        return f"Order {self.order_id} - {self.client.company_name}"

class OrderModificationRequest(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='modifications')
    request_text = models.TextField()
    is_approved = models.BooleanField(default=False, null=True) # Null means pending
    created_at = models.DateTimeField(auto_now_add=True)

class ChatMessage(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='chat_logs')
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True) # Admin/Manufacturer or Customer
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)