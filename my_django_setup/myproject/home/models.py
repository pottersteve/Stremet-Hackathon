from django.contrib.auth.models import User
from django.db import models


class UserProfile(models.Model):
    ROLE_CHOICES = (
        ("admin", "Administrator"),
        ("customer", "Customer"),
        ("manufacturer", "Manufacturer"),
        ("designer", "Designer"),
        ("warehouse", "Warehouse"),
    )
    # Links this profile to the built-in Django User (which handles name, email, password)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="customer")

    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()}"


class Client(models.Model):
    name = models.CharField(max_length=200, blank=True, null=True)
    email = models.EmailField(unique=True)
    company_name = models.CharField(max_length=200)

    def __str__(self):
        return self.company_name


class Order(models.Model):
    STAGE_CHOICES = [
        ("order_received", "Order Received"),
        ("raw_materials", "Raw Materials Preparation"),
        ("melting", "Melting & Refining"),
        ("casting", "Continuous Casting"),
        ("rolling", "Hot/Cold Rolling"),
        ("finishing", "Finishing & Inspection"),
        ("shipping", "Ready for Shipping"),
        ("delivered", "Delivered"),
    ]

    order_id = models.CharField(max_length=50, unique=True)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="orders")

    steel_grade = models.CharField(max_length=50)
    product_form = models.CharField(max_length=50, blank=True, null=True)
    dimensions = models.CharField(max_length=100)
    quantity_tons = models.DecimalField(max_digits=10, decimal_places=2)
    surface_finish = models.CharField(max_length=50, blank=True, null=True)

    heat_treatment = models.BooleanField(default=False)
    ultrasonic_test = models.BooleanField(default=False)
    mill_certificate = models.BooleanField(default=False)

    blueprint_file = models.FileField(upload_to="blueprints/", blank=True, null=True)
    admin_notes = models.TextField(blank=True, null=True)

    status = models.CharField(
        max_length=30, choices=STAGE_CHOICES, default="order_received"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    target_delivery = models.DateField()

    def __str__(self):
        return f"{self.order_id} - {self.client.company_name} ({self.get_status_display()})"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    item_name = models.CharField(
        max_length=255, help_text="e.g., 304 Stainless Steel Bracket Assembly"
    )
    quantity = models.PositiveIntegerField(default=1)

    # The 5 Manufacturing Steps
    step_1_programming = models.BooleanField(default=False)
    step_2_cutting = models.BooleanField(default=False)
    step_3_forming = models.BooleanField(default=False)
    step_4_joining = models.BooleanField(default=False)
    step_5_delivery = models.BooleanField(default=False)

    @property
    def current_status(self):
        """Dynamically calculates the current flowchart stage."""
        if self.step_5_delivery:
            return "Delivery / 3rd Party"
        if self.step_4_joining:
            return "Joining & Assembling"
        if self.step_3_forming:
            return "Forming & Bending"
        if self.step_2_cutting:
            return "Cutting (2D)"
        if self.step_1_programming:
            return "Programming / Designing"
        return "Pending"

    def __str__(self):
        return f"{self.item_name} (Order: {self.order.order_id}) - Status: {self.current_status}"


class OrderImage(models.Model):
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="reference_images"
    )
    image = models.ImageField(upload_to="order_references/")
    uploaded_at = models.DateTimeField(auto_now_add=True)


class OrderModificationRequest(models.Model):
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="modifications"
    )
    request_text = models.TextField()
    is_approved = models.BooleanField(default=False, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class ChatMessage(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="chat_logs")
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    message = models.TextField()

    step_context = models.CharField(
        max_length=255, blank=True, null=True, help_text="The flowchart step clicked"
    )
    attachment = models.FileField(upload_to="chat_attachments/", blank=True, null=True)

    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order {self.order.order_id} - Msg from {self.sender.username}"
