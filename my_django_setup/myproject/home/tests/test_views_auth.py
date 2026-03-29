import pytest
from django.urls import reverse


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
