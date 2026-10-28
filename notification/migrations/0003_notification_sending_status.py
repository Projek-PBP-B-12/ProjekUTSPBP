from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("notification", "0002_notification_email_sent_at_notification_email_status_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="notification",
            name="email_status",
            field=models.CharField(
                max_length=10,
                default="SKIPPED",
                choices=[
                    ("SKIPPED", "Tidak dikirim"),
                    ("PENDING", "Menunggu"),
                    ("SENDING", "Sedang diproses"),
                    ("SENT", "Diterima layanan email"),
                    ("FAILED", "Gagal"),
                ],
            ),
        ),
    ]
