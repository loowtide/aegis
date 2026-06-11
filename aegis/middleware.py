from collections.abc import Callable

from django.conf import settings
from django.db.models import F, Q
from django.http import HttpRequest, HttpResponse
from django.template.loader import render_to_string
from django.utils import timezone

from aegis.models import BlockedIP
from aegis.rate_limit import (
    auto_block,
    increment_violations,
    is_rate_limited,
    #    reset_if_clean_window,
)
from aegis.utils import get_client_ip


def _humanize(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds} second{'s' if seconds != 1 else ''}"
    if seconds < 3600:
        m = seconds // 60
        return f"{m} minute{'s' if m != 1 else ''}"
    if seconds < 86400:
        h = seconds // 3600
        return f"{h} hour{'s' if h != 1 else ''}"
    d = seconds // 86400
    return f"{d} day{'s' if d != 1 else ''}"


class BlockedIPMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        ip = get_client_ip(request)
        if not ip:
            return self.get_response(request)
        now = timezone.now()
        entry = BlockedIP.objects.filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=now), ip=ip
        ).first()
        if entry:
            BlockedIP.objects.filter(pk=entry.pk).update(
                last_seen=now, tally=F("tally") + 1
            )
            if entry.expires_at is None:
                retry_after = None
            else:
                retry_after = max(1, int((entry.expires_at - now).total_seconds()))
            html = render_to_string(
                "aegis/403.html",
                {
                    "retry_after_human": _humanize(retry_after)
                    if retry_after
                    else "the foreseeable future"
                },
                request=request,
            )
            response = HttpResponse(html, status=403)
            if retry_after is not None:
                response["Retry-After"] = str(retry_after)
            return response
        return self.get_response(request)


class RateLimitMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if not self._should_rate_limit(request):
            return self.get_response(request)
        ip = get_client_ip(request)
        if not ip:
            return self.get_response(request)
        window = getattr(settings, "AEGIS_RATE_LIMIT_WINDOW", 60)
        max_requests = getattr(settings, "AEGIS_RATE_LIMIT_REQUESTS", 100)
        auto_block_enabled = getattr(settings, "AEGIS_RATE_LIMIT_AUTO_BLOCK", True)
        threshold = getattr(settings, "AEGIS_RATE_LIMIT_AUTO_BLOCK_THRESHOLD", 5)
        block_duration = getattr(settings, "AEGIS_RATE_LIMIT_BLOCK_DURATION", 3600)
        limited, _ = is_rate_limited(ip, max_requests, window)
        if limited:
            violations = increment_violations(ip, window, threshold)
            if auto_block_enabled and violations >= threshold:
                auto_block(ip, block_duration)
            retry_after = window
            html = render_to_string(
                "aegis/429.html",
                {"retry_after_human": _humanize(retry_after)},
                request=request,
            )
            response = HttpResponse(html, status=429)
            response["Retry-After"] = str(retry_after)
            return response
        return self.get_response(request)

    def _should_rate_limit(self, request: HttpRequest) -> bool:
        if not getattr(settings, "AEGIS_RATE_LIMIT_ENABLED", True):
            return False
        skip_paths = getattr(settings, "AEGIS_RATE_LIMIT_SKIP_PATHS", [])
        path = request.path_info
        return not any(path.startswith(p) for p in skip_paths)
