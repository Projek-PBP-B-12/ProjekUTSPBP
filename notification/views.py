from datetime import timedelta
from smtplib import SMTPException

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.mail import BadHeaderError, send_mail
from django.core.validators import validate_email
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from FoodItem.models import FoodItem
from .models import Notification


REMINDER_DAYS = (7, 3, 1)
ACTIVE_FOOD_STATUSES = ("STORED", "OFFERED")


@login_required(login_url="admin:login")
@require_GET
def show_notification(request):
    notifications = Notification.objects.filter(
        recipient=request.user,
    ).select_related("food_item")

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

@require_POST
def mark_notification_read(request, pk):
    if not request.user.is_authenticated:
        return JsonResponse(
            {"message": "Silakan login kembali."},
            status=401,
        )

    notifications = Notification.objects.filter(
        recipient=request.user,
    )

    updated = notifications.filter(pk=pk).update(is_read=True)

    if not updated:
        return JsonResponse(
            {"message": "Notifikasi tidak ditemukan."},
            status=404,
        )

    return JsonResponse({
        "success": True,
        "unread_count": notifications.filter(is_read=False).count(),
    })


def generate_food_reminders(dry_run=False):
    """Baca ulang makanan aktif; buat satu pesan per tahap dan tanggal."""
    today = timezone.localdate()
    checked_count = 0
    created_count = 0

    for days in REMINDER_DAYS:
        expiry_date = today + timedelta(days=days)
        foods = FoodItem.objects.filter(
            expiration_date=expiry_date,
            status__in=ACTIVE_FOOD_STATUSES,
        )

        for food in foods:
            checked_count += 1
            if dry_run:
                continue

            _, created = Notification.objects.get_or_create(
                recipient_id=food.owner_id,
                food_item=food,
                reminder_days=days,
                expiry_date=food.expiration_date,
                defaults={
                    "title": f"Pengingat H-{days}: {food.name}",
                    "message": (
                        f"{food.name} diperkirakan kedaluwarsa "
                        f"{days} hari lagi, pada "
                        f"{food.expiration_date:%d/%m/%Y}. "
                        "Periksa kondisi makanan dan tentukan langkah berikutnya."
                    ),
                    "email_status": Notification.EmailStatus.PENDING,
                },
            )
            created_count += int(created)

    return {"checked": checked_count, "created": created_count}


def send_reminder_email(notification_id):
    """Periksa ulang kondisi terkini sebelum mengirim satu email."""
    notification = Notification.objects.select_related(
        "recipient", "food_item",
    ).filter(pk=notification_id).first()

    if notification is None:
        return Notification.EmailStatus.SKIPPED

    if notification.email_status not in (
        Notification.EmailStatus.PENDING,
        Notification.EmailStatus.FAILED,
    ):
        return notification.email_status

    food = notification.food_item
    reason = ""

    if notification.reminder_days not in REMINDER_DAYS:
        reason = "Notifikasi ini bukan pengingat H-7, H-3, atau H-1."
    elif food is None:
        reason = "Makanan sudah dihapus."
    elif food.status not in ACTIVE_FOOD_STATUSES:
        reason = "Makanan sudah tidak aktif."
    elif food.owner_id != notification.recipient_id:
        reason = "Pemilik makanan telah berubah."
    elif food.expiration_date != notification.expiry_date:
        reason = "Tanggal kedaluwarsa telah berubah."
    elif (
        food.expiration_date - timezone.localdate()
    ).days != notification.reminder_days:
        reason = "Tanggal tahap pengingat ini sudah lewat atau belum berlaku."

    email = notification.recipient.email.strip()
    if not reason:
        try:
            validate_email(email)
        except ValidationError:
            reason = "Alamat email penerima kosong atau tidak valid."

    if reason:
        notification.email_status = Notification.EmailStatus.SKIPPED
        notification.last_email_error = reason
        notification.save(update_fields=["email_status", "last_email_error"])
        return notification.email_status

    url = settings.SITE_URL.rstrip("/") + reverse(
        "notification:show_notification",
    )
    body = (
        f"Halo {notification.recipient.get_username()},\n\n"
        f"{notification.title}\n\n"
        f"{notification.message}\n\n"
        f"Lihat notifikasi: {url}\n\n"
        "Salam,\nTitikLapar"
    )

    try:
        sent = send_mail(
            subject=" ".join(f"[TitikLapar] {notification.title}".splitlines()),
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
        if sent != 1:
            raise SMTPException("Layanan email tidak menerima pesan.")
    except (SMTPException, OSError, BadHeaderError) as error:
        notification.email_status = Notification.EmailStatus.FAILED
        notification.last_email_error = str(error)[:1000]
        notification.save(update_fields=["email_status", "last_email_error"])
        return notification.email_status

    notification.email_status = Notification.EmailStatus.SENT
    notification.email_sent_at = timezone.now()
    notification.last_email_error = ""
    notification.save(update_fields=[
        "email_status", "email_sent_at", "last_email_error",
    ])
    return notification.email_status


def send_pending_reminder_emails():
    """Proses pesan menunggu/gagal; riwayat manual dan SENT tidak dikirim."""
    notification_ids = list(Notification.objects.filter(
        reminder_days__in=REMINDER_DAYS,
        email_status__in=[
            Notification.EmailStatus.PENDING,
            Notification.EmailStatus.FAILED,
        ],
    ).values_list("pk", flat=True))

    result = {"sent": 0, "failed": 0, "skipped": 0}
    result_keys = {
        Notification.EmailStatus.SENT: "sent",
        Notification.EmailStatus.FAILED: "failed",
        Notification.EmailStatus.SKIPPED: "skipped",
    }

    for notification_id in notification_ids:
        status = send_reminder_email(notification_id)
        result[result_keys[status]] += 1

    return result
