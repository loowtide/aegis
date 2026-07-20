import pytest
from django.test import RequestFactory, override_settings

from aegis.utils import _is_trusted, get_client_ip


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


@pytest.mark.django_db
class TestIsTrustedIPv4Only:
    def test_trusts_loopback_by_default(self) -> None:
        assert _is_trusted("127.0.0.1") is True

    def test_trusts_ip_in_configured_cidr(self) -> None:
        with override_settings(AEGIS_TRUSTED_PROXY_NETWORKS=["10.0.0.0/8"]):
            from aegis import utils

            utils.TRUSTED_PROXY_NETWORKS = utils._load_trusted_networks()
            assert _is_trusted("10.1.2.3") is True
            assert _is_trusted("11.1.2.3") is False
        from aegis import utils

        utils.TRUSTED_PROXY_NETWORKS = utils._load_trusted_networks()

    def test_rejects_ipv6_even_if_supplied(self) -> None:
        assert _is_trusted("::1") is False

    def test_rejects_garbage(self) -> None:
        assert _is_trusted("not-an-ip") is False
        assert _is_trusted("") is False


@pytest.mark.django_db
class TestGetClientIpSpoofing:
    def test_attacker_prepended_entries_are_ignored(self) -> None:
        factory = RequestFactory()
        request = factory.get(
            "/", REMOTE_ADDR="127.0.0.1", HTTP_X_FORWARDED_FOR="9.9.9.9, 198.51.100.7"
        )
        assert get_client_ip(request) == "198.51.100.7"

    def test_depth_two_requires_two_hops(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from aegis import utils

        monkeypatch.setattr(utils, "TRUSTED_PROXY_DEPTH", 2)
        factory = RequestFactory()
        request = factory.get(
            "/",
            REMOTE_ADDR="127.0.0.1",
            HTTP_X_FORWARDED_FOR="9.9.9.9, 10.0.0.5, 198.51.100.7",
        )
        assert get_client_ip(request) == "10.0.0.5"

    def test_short_header_falls_back_to_remote_addr(self) -> None:
        from aegis import utils

        factory = RequestFactory()
        request = factory.get(
            "/", REMOTE_ADDR="127.0.0.1", HTTP_X_FORWARDED_FOR="198.51.100.7"
        )
        with override_settings(AEGIS_TRUSTED_PROXY_DEPTH=3):
            utils.TRUSTED_PROXY_DEPTH = 3
            assert get_client_ip(request) == "127.0.0.1"
        utils.TRUSTED_PROXY_DEPTH = 1
