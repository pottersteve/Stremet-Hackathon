from django.urls import reverse


def test_login_and_logout_url_names_resolve():
    assert reverse("login") == "/login/"
    assert reverse("logout") == "/logout/"
