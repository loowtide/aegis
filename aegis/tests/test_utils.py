import pytest
from django.test import RequestFactory

from aegis.utils import get_client_ip


@pytest.mark.django_db
class TestUtils:
    def test_get_client_ip_for_direct_conn(self) -> None:
        """get ip address for direct connection."""

        factory = RequestFactory()
        request = factory.get("/", REMOTE_ADDR="127.0.0.2")
        assert get_client_ip(request) == "127.0.0.2"

    def test_get_client_ip_from_x_forwarded_for_trusted(self) -> None:
        factory = RequestFactory()
        request = factory.get(
            "/", REMOTE_ADDR="127.0.0.1", HTTP_X_FORWARDED_FOR="223.20.1.0"
        )
        assert get_client_ip(request) == "223.20.1.0"

    def test_get_client_ip_from_x_forwarded_for_untrusted(self) -> None:
        factory = RequestFactory()
        request = factory.get(
            "/", REMOTE_ADDR="127.0.0.2", HTTP_X_FORWARDED_FOR="10.0.0.2"
        )
        assert get_client_ip(request) == "127.0.0.2"
