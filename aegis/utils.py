import ipaddress
import logging
from datetime import datetime
from typing import Any

from django.conf import settings
from django.db.models import Q
from django.http import HttpRequest
from django.utils import timezone

from aegis.models import BlockedIP

logger = logging.getLogger(__name__)


def _load_trusted_networks() -> list[ipaddress.IPv4Network]:
    raw = getattr(settings, "AEGIS_TRUSTED_PROXY_NETWORKS", ["127.0.0.1"])
    networks = []
    for entry in raw:
        try:
            networks.append(ipaddress.ip_network(entry, strict=False))
        except ValueError:
            logger.warning("aegis: ignoring invalid trusted proxy network %r", entry)
    return networks


TRUSTED_PROXY_NETWORKS = _load_trusted_networks()
TRUSTED_PROXY_DEPTH = getattr(settings, "AEGIS_TRUSTED_PROXY_DEPTH")


def _is_trusted(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(
        addr in net
        for net in TRUSTED_PROXY_NETWORKS
        if isinstance(net, ipaddress.IPv4Network)
    )


def get_client_ip(request: HttpRequest) -> Any:
    remote_addr = request.META.get("REMOTE_ADDR")
    if not remote_addr or not _is_trusted(remote_addr):
        return remote_addr
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if not xff:
        return remote_addr

    hops = [h.strip() for h in xff.split(",") if h.strip()]
    if not hops:
        return remote_addr

    if TRUSTED_PROXY_DEPTH < 1:
        logger.warning("aegis: AEGIS_PROXY_DEPTH <1 ,XFF ignored")
        return remote_addr

    if len(hops) < TRUSTED_PROXY_DEPTH:
        logger.warning(
            "aegis: XFF has  %d hop(s), expected at least %d, falling to REMOTE_ADDR",
            len(hops),
            TRUSTED_PROXY_DEPTH,
        )
        return remote_addr

    client_ip = hops[-TRUSTED_PROXY_DEPTH]
    try:
        ipaddress.ip_address(client_ip)
    except ValueError:
        logger.warning("aegis: XFF client entry %r is not valid IP", client_ip)
        return remote_addr
    return client_ip


def should_block(ip: str, now: datetime | None = None) -> BlockedIP | None:
    now = now or timezone.now()
    return BlockedIP.objects.filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=now), ip=ip
    ).first()
