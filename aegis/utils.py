from django.conf import settings

from .models import BlockedIP, HttpMethod, RateLimit


def get_client_ip(request) -> str:
    if x_forwarded_for := request.META.get("HTTP_X_FORWARDED_FOR"):
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def should_block(request: HttpMethod) -> bool:
    ip = get_client_ip(request)
    try:
        record = BlockedIP.objects.filter(ip=get_client_ip(request)).first()
        curr_method = request.method.upper()
    except ValueError:
        return False
    try:
        method_flag = getattr(HttpMethod, curr_method, None)
        if method_flag is None:
            return False
        is_allowed = bool(record.allowed_methods & method_flag)
        return not is_allowed
    except AttributeError:
        return False
    return method_flag not in record.allowed_methods
