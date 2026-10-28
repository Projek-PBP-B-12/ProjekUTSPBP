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


@login_required
@require_GET
def show_notification(request):
    """Tampilkan notifikasi milik pengguna yang sedang login."""
    generate_food_reminders(recipient=request.user)
    notifications = Notification.objects.filter(
        recipient=request.user,
    ).select_related("food_item")

    context = {
        "page_title": "Notifikasi",
        "page_summary": "Pengingat tentang makananmu. Keputusan tetap ada padamu.",
        "notifications": notifications,
        "unread_count": notifications.filter(is_read=False).count(),
    }
    return render(request, "notification/list.html", context)


@require_POST
def mark_notification_read(request, pk):
    """Ubah status baca, tanpa mengubah status makanan atau email."""
    if not request.user.is_authenticated:
        return JsonResponse({"message": "Silakan login kembali."}, status=401)

    notifications = Notification.objects.filter(recipient=request.user)
    updated = notifications.filter(pk=pk).update(is_read=True)

    if not updated:
        return JsonResponse({"message": "Notifikasi tidak ditemukan."}, status=404)

    return JsonResponse({
        "success": True,
        "unread_count": notifications.filter(is_read=False).count(),
    })


def generate_food_reminders(dry_run=False, recipient=None, food_item=None):
    """Cari makanan aktif pada H-7, H-3, dan H-1; buat pesan jika belum ada."""
    today = timezone.localdate()
    result = {"checked": 0, "created": 0}

    for days in REMINDER_DAYS:
        foods = FoodItem.objects.filter(
            expiration_date=today + timedelta(days=days),
            status__in=ACTIVE_FOOD_STATUSES,
        )
        if recipient is not None:
            foods = foods.filter(owner=recipient)
        if food_item is not None:
            foods = foods.filter(pk=food_item.pk)

        for food in foods:
            result["checked"] += 1
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
                        f"{food.name} diperkirakan kedaluwarsa {days} hari lagi, "
                        f"pada {food.expiration_date:%d/%m/%Y}. "
                        "Periksa kondisi makanan dan tentukan langkah berikutnya."
                    ),
                    "email_status": Notification.EmailStatus.PENDING,
                },
            )
            if created:
                result["created"] += 1

    return result


def send_reminder_email(notification_id):
    """Periksa kondisi makanan, kirim email, lalu simpan hasilnya."""
    notification = Notification.objects.select_related(
        "recipient", "food_item",
    ).filter(pk=notification_id).first()

    if notification is None:
        return Notification.EmailStatus.SKIPPED
    if notification.email_status not in (
        Notification.EmailStatus.PENDING, Notification.EmailStatus.FAILED,
    ):
        return notification.email_status

    food = notification.food_item
    email = notification.recipient.email.strip()
    error = ""

    if notification.reminder_days not in REMINDER_DAYS:
        error = "Notifikasi ini bukan pengingat H-7, H-3, atau H-1."
    elif food is None:
        error = "Makanan sudah dihapus."
    elif food.status not in ACTIVE_FOOD_STATUSES:
        error = "Makanan sudah tidak aktif."
    elif food.owner_id != notification.recipient_id:
        error = "Pemilik makanan telah berubah."
    elif food.expiration_date != notification.expiry_date:
        error = "Tanggal kedaluwarsa telah berubah."
    elif (food.expiration_date - timezone.localdate()).days != notification.reminder_days:
        error = "Tanggal tahap pengingat ini sudah lewat atau belum berlaku."

    if not error:
        try:
            validate_email(email)
        except ValidationError:
            error = "Alamat email penerima kosong atau tidak valid."

    status = Notification.EmailStatus.SKIPPED
    sent_at = None

    if not error:
        url = settings.SITE_URL.rstrip("/") + reverse("notification:show_notification")
        message = (
            f"Halo {notification.recipient.get_username()},\n\n"
            f"{notification.title}\n\n{notification.message}\n\n"
            f"Lihat notifikasi: {url}\n\nSalam,\nTitikLapar"
        )
        subject = " ".join(f"[TitikLapar] {notification.title}".splitlines())

        try:
            sent = send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )
            if sent != 1:
                raise SMTPException("Layanan email tidak menerima pesan.")
            status = Notification.EmailStatus.SENT
            sent_at = timezone.now()
        except (SMTPException, OSError, BadHeaderError) as exception:
            status = Notification.EmailStatus.FAILED
            error = str(exception)[:1000]

    # 3. Simpan hasil pengiriman tanpa menimpa status baca pengguna.
    Notification.objects.filter(pk=notification.pk).update(
        email_status=status,
        email_sent_at=sent_at,
        last_email_error=error,
    )
    return status


def send_pending_reminder_emails(food_item=None):
    """Proses email yang menunggu/gagal, kemudian hitung hasilnya."""
    notifications = Notification.objects.filter(
        reminder_days__in=REMINDER_DAYS,
        email_status__in=[
            Notification.EmailStatus.PENDING,
            Notification.EmailStatus.FAILED,
        ],
    )
    # Saat menyimpan makanan, kirim hanya pengingat milik makanan itu.
    if food_item is not None:
        notifications = notifications.filter(
            food_item=food_item, recipient_id=food_item.owner_id,
        )
    notifications = list(notifications)
    result = {"sent": 0, "failed": 0, "skipped": 0}

    for notification in notifications:
        status = send_reminder_email(notification.pk)

        if status == Notification.EmailStatus.SENT:
            result["sent"] += 1
        elif status == Notification.EmailStatus.FAILED:
            result["failed"] += 1
        else:
            result["skipped"] += 1

    return result
