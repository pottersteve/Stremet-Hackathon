from datetime import date

import pytest
from django.contrib.auth.models import User

from home.models import Client, Order, OrderItem, UserProfile


@pytest.fixture
def django_user(db):
    user = User.objects.create_user(
        username="staff",
        password="secret",
        email="staff@example.com",
    )
    UserProfile.objects.get_or_create(user=user, defaults={"role": "admin"})
    return user


@pytest.fixture
def order_with_item(db):
    client = Client.objects.create(email="client@example.com", company_name="ACME")
    order = Order.objects.create(
        order_id="TEST-ORDER-1",
        client=client,
        target_delivery=date.today(),
        steel_grade="S355",
        dimensions="10mm x 20mm x 30mm",
        quantity_tons=1,
    )
    item = OrderItem.objects.create(order=order, item_name="Widget")
    return order, item
