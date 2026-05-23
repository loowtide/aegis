
# Aegis 
Django middleware that blocks requests from IPs listed in a database-backed blocklist. Returns a styled 403 response with a `Retry-After` header and tracks every blocked attempt.

## Features

- Database-backed blocklist with per-entry expiry
- Atomic tally and `last_seen` tracking on each hit
- Standards-compliant `Retry-After` header
- Human-readable retry duration in the rendered template
- Expired entries ignored automatically

## Installation

Add the middleware to `MIDDLEWARE` in `settings.py`. Place it early so blocked requests short-circuit before auth, sessions, and views:

```python
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "aegis.middleware.BlockedIPMiddleware",
    # ...
]
```

Ensure `aegis` is in `INSTALLED_APPS`, then run migrations:

```bash
python manage.py migrate aegis
```

## Requirements

| Component | Purpose |
|---|---|
| `aegis.models.BlockedIP` | Model with fields: `ip`, `expires_at`, `last_seen`, `tally` |
| `aegis.utils.get_client_ip` | Extracts the real client IP from the request |
| `aegis/blocked.html` | Template rendered for blocked requests; receives `retry_after_human` |

A minimal template:

```html
<!DOCTYPE html>
<html>
  <head><title>Blocked</title></head>
  <body>
    <h1>You are temporarily blocked</h1>
    <p>Try again in {{ retry_after_human }}.</p>
  </body>
</html>
```

## How It Works

On every request, the middleware:

1. Resolves the client IP via `get_client_ip(request)`.
2. Looks up an active `BlockedIP` record (`expires_at > now`).
3. If none exists, the request proceeds normally.
4. If one exists:
   - Atomically increments `tally` and updates `last_seen` using `F()`.
   - Computes seconds remaining until `expires_at`.
   - Renders `aegis/blocked.html` with a humanized duration.
   - Returns `403 Forbidden` with a `Retry-After` header.

## Response Format

- **Status:** `403 Forbidden`
- **Header:** `Retry-After: <seconds>` — minimum `1`, honored by well-behaved clients and crawlers
- **Body:** Rendered HTML from `aegis/blocked.html`

## Humanized Durations

The `_humanize` helper converts seconds into the largest unit that fits, with correct pluralization:

| Range | Output |
|---|---|
| `< 60s` | `"42 seconds"` |
| `< 60m` | `"7 minutes"` |
| `< 24h` | `"3 hours"` |
| `≥ 24h` | `"2 days"` |

## Adding a Block

Create a `BlockedIP` row anywhere in your code — a signal, management command, admin action, or rate-limit handler:

```python
from datetime import timedelta
from django.utils import timezone
from aegis.models import BlockedIP

BlockedIP.objects.create(
    ip="203.0.113.45",
    expires_at=timezone.now() + timedelta(hours=1),
)
```

The block takes effect on the offender's next request — no restart or cache invalidation needed.
