from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "recipient",
        "reminder_days",
        "expiry_date",
        "is_read",
        "email_status",
        "created_at",
    )

    list_filter = (
        "reminder_days",
        "is_read",
        "email_status",
    )

    search_fields = (
        "title",
        "message",
        "recipient__username",
    )

    readonly_fields = (
        "created_at",
        "reminder_days",
        "expiry_date",
        "email_status",
        "email_sent_at",
        "last_email_error",
    )