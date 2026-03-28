import pytest
from django.test import Client
from django.urls import resolve, reverse

from home.views import customer_panel


def test_customer_panel_reverse_and_resolves_to_home_view():
    assert reverse("customer_panel") == "/customer/"
    match = resolve("/customer/")
    assert match.func == customer_panel


@pytest.mark.django_db
def test_customer_panel_post_finds_order(order_with_item):
    order, _item = order_with_item
    client = Client()
    response = client.post(
        reverse("customer_panel"),
        {"order_id": order.order_id},
    )
    assert response.status_code == 200
    assert response.context["order"].pk == order.pk


@pytest.mark.django_db
def test_customer_panel_post_unknown_order_shows_message():
    client = Client()
    response = client.post(
        reverse("customer_panel"),
        {"order_id": "no-such-id"},
    )
    assert response.status_code == 200
    assert response.context["order"] is None
