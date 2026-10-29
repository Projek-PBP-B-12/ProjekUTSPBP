from datetime import timedelta
from functools import wraps
from math import ceil

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.db.models import Case, F, Q, Value, When
from django.shortcuts import render
from django.utils import timezone
from django.utils.cache import add_never_cache_headers

from .models import SharedPostWriteQuota


def _take_write_slot(user_id, limit, window_seconds):
    """Reserve a slot with a conditional SQL update shared by all workers.

    Returns zero when allowed, otherwise the remaining wait in seconds.
    Counters are deliberately committed before the view's own transaction:
    invalid input and failed mutations must still consume an attempt.
    """
    now = timezone.now()
    expired = Q(window_started_at__lte=now - timedelta(seconds=window_seconds))
    with transaction.atomic():
        SharedPostWriteQuota.objects.get_or_create(
            user_id=user_id,
            defaults={"window_started_at": now, "request_count": 0},
        )
        bucket = SharedPostWriteQuota.objects.filter(user_id=user_id)
        reserved = bucket.filter(expired | Q(request_count__lt=limit)).update(
            request_count=Case(
                When(expired, then=Value(1)), default=F("request_count") + 1,
            ),
            window_started_at=Case(
                When(expired, then=Value(now)), default=F("window_started_at"),
            ),
        )
        if reserved:
            return 0
        started_at = bucket.values_list("window_started_at", flat=True).get()
    return max(1, ceil((started_at + timedelta(seconds=window_seconds) - now).total_seconds()))


def limit_sharedpost_writes(view):
    """Limit authenticated POSTs; use below login and HTTP-method decorators."""
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if request.method != "POST" or not request.user.is_authenticated:
            return view(request, *args, **kwargs)

        limit = getattr(settings, "SHAREDPOST_WRITE_LIMIT", 20)
        window = getattr(settings, "SHAREDPOST_WRITE_WINDOW_SECONDS", 60)
        if type(limit) is not int or type(window) is not int or limit < 1 or window < 1:
            raise ImproperlyConfigured("Batas request SharedPost harus berupa bilangan bulat positif.")
        retry_after = _take_write_slot(request.user.pk, limit, window)
        if not retry_after:
            return view(request, *args, **kwargs)

        response = render(
            request, "SharedPost/rate_limited.html",
            {"retry_after": retry_after}, status=429,
        )
        response["Retry-After"] = str(retry_after)
        add_never_cache_headers(response)
        return response

    return wrapped
