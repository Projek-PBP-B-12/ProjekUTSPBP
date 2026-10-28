from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from notification.views import generate_food_reminders, send_pending_reminder_emails


class Command(BaseCommand):
    help = "Buat dan proses pengingat makanan H-7, H-3, dan H-1. Jalankan setiap hari."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Hitung makanan yang memenuhi syarat, tanpa menyimpan atau mengirim email.",
        )

    def handle(self, *args, **options):
        generated = generate_food_reminders(dry_run=options["dry_run"])
        self.stdout.write(f"Makanan diperiksa: {generated['checked']}; notifikasi baru: {generated['created']}.")
        if options["dry_run"]:
            self.stdout.write("Dry run: database tidak diubah dan email tidak dikirim.")
            return

        self.stdout.write(f"Backend email: {settings.EMAIL_BACKEND}")
        if settings.EMAIL_BACKEND == "django.core.mail.backends.console.EmailBackend":
            self.stdout.write("Mode console: isi email hanya dicetak ke terminal, bukan dikirim ke kotak masuk.")
        result = send_pending_reminder_emails()
        self.stdout.write(
            f"Diterima backend: {result['sent']}; gagal: {result['failed']}; "
            f"dilewati: {result['skipped']}; sedang diproses worker lain: {result['in_progress']}."
        )
        if result["failed"]:
            raise CommandError("Sebagian email gagal; lihat Notification.last_email_error sebelum mencoba lagi.")
