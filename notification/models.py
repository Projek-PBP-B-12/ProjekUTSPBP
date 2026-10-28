from django.conf import settings
from django.db import models


class Notification(models.Model):
    class EmailStatus(models.TextChoices):
        SKIPPED = "SKIPPED", "Tidak dikirim"
        PENDING = "PENDING", "Menunggu"
        SENDING = "SENDING", "Sedang diproses"
        SENT = "SENT", "Diterima layanan email"
        FAILED = "FAILED", "Gagal"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )

    food_item = models.ForeignKey(
        "FoodItem.FoodItem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
    )

    title = models.CharField(max_length=200)

    message = models.TextField()

    is_read = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    reminder_days = models.PositiveSmallIntegerField(
        choices=[
            (7, "H-7"),
            (3, "H-3"),
            (1, "H-1"),
        ],
        null=True,
        blank=True,
    )

    expiry_date = models.DateField(
        null=True,
        blank=True,
    )

    email_status = models.CharField(
        max_length=10,
        choices=EmailStatus.choices,
        default=EmailStatus.SKIPPED,
    )

    email_sent_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    last_email_error = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "-pk"]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "recipient",
                    "food_item",
                    "reminder_days",
                    "expiry_date",
                ],
                name="unique_food_expiry_reminder",
            ),
        ]

    def __str__(self):
        return self.title
