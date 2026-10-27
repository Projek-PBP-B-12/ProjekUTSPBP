from datetime import timedelta

from django.db.models import Count, Q
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.cache import never_cache

from FoodItem.models import FoodItem
from SharedPost.models import SharedPost
from notification.models import Notification


@never_cache
def landing_page(request):
    if not request.user.is_authenticated:
        return render(request, "index.html")

    today = timezone.localdate()
    foods = FoodItem.objects.filter(owner=request.user)
    needs_attention = Q(
        status__in=("STORED", "OFFERED"),
        expiration_date__range=(today, today + timedelta(days=3)),
    )
    summary = foods.aggregate(
        stored_count=Count("pk", filter=Q(status="STORED")),
        attention_count=Count("pk", filter=needs_attention),
    )
    active_posts = SharedPost.objects.filter(
        food_item__owner=request.user,
        food_item__status="OFFERED",
        food_item__expiration_date__gte=today,
        is_active=True,
    )
    unread = Notification.objects.filter(recipient=request.user, is_read=False)

    return render(request, "dashboard.html", {
        **summary,
        "shared_count": active_posts.count(),
        "attention_foods": foods.filter(needs_attention).order_by("expiration_date", "pk")[:3],
        "active_posts": active_posts.select_related("food_item", "location").order_by(
            "food_item__expiration_date", "pk",
        )[:3],
        "display_name": request.user.get_full_name().strip() or request.user.get_username(),
        "quick_notifications": unread[:3],
    })
