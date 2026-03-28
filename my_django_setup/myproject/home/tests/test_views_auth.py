import json

import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_update_item_status_requires_login(client, order_with_item):
    _order, item = order_with_item
    url = reverse("update_item_status")
    resp = client.post(
        url,
        data=json.dumps({"item_id": item.pk, "step": 1, "is_done": True}),
        content_type="application/json",
    )
    assert resp.status_code == 302
    assert "login" in resp["Location"]


@pytest.mark.django_db
def test_update_item_status_authenticated(client, django_user, order_with_item):
    client.force_login(django_user)
    _order, item = order_with_item
    url = reverse("update_item_status")
    resp = client.post(
        url,
        data=json.dumps({"item_id": item.pk, "step": 1, "is_done": True}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


@pytest.mark.django_db
def test_send_chat_message_anonymous_allowed(client, order_with_item):
    order, _item = order_with_item
    url = reverse("send_chat_message")
    resp = client.post(
        url,
        data={"order_id": order.order_id, "chat_message": "hello"},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True
