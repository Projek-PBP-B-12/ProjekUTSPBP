from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .models import Notification


@login_required(login_url="admin:login")
@require_GET
def show_notification(request):
    notifications = Notification.objects.filter(
        recipient=request.user,
    )

    unread_count = notifications.filter(
        is_read=False,
    ).count()

    context = {
        "page_title": "Notifikasi",
        "page_summary": (
            "Pengingat tentang makananmu. "
            "Keputusan tetap ada padamu."
        ),
        "notifications": notifications,
        "unread_count": unread_count,
    }

    return render(
        request,
        "notification/list.html",
        context,
    )