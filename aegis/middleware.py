from django.db.models import F
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils import timezone

from aegis.models import BlockedIP
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
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ip = get_client_ip(request)
        now = timezone.now()
        entry = BlockedIP.objects.filter(ip=ip, expires_at__gt=now).first()
        if entry:
            BlockedIP.objects.filter(pk=entry.pk).update(
                last_seen=now, tally=F("tally") + 1
            )
            retry_after = max(1, int((entry.expires_at - now).total_seconds()))
            html = render_to_string(
                "aegis/blocked.html",
                {"retry_after_human": _humanize(retry_after)},
                request=request,
            )
            response = HttpResponse(html, status=403)
            response["Retry-After"] = str(retry_after)
            return response
        return self.get_response(request)
