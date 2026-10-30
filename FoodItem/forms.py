from django.forms import ModelForm, TextInput, Textarea, URLInput, NumberInput, DateInput
from django.core.exceptions import ValidationError
from django.utils.html import strip_tags
from urllib.parse import urlsplit

from .models import *

class FoodItemForm(ModelForm):
    class Meta:
        model = FoodItem
        fields = [
            "name",
            "category",
            "purchase_date",
            "expiration_date",
            "image_url",
        ]

        labels = {
            "name": "Nama Makanan",
            "category": "Kategori",
            "purchase_date": "Tanggal Beli (opsional)",
            "expiration_date": "Tanggal Kedaluwarsa (opsional)",
            "image_url": "URL Foto (opsional)",
        }

        help_texts = {
            "purchase_date": "Jika kosong, akan digunakan tanggal hari ini.",
            "expiration_date": "Jika kosong, akan digunakan tanggal hari ini.",
            "image_url": "Gunakan tautan gambar HTTP/HTTPS atau tautan berbagi Google Drive yang dapat diakses publik. Tautan halaman web biasa tidak dapat ditampilkan sebagai foto.",
        }

        widgets = {
            "purchase_date": DateInput(attrs={"type": "date"}),
            "expiration_date": DateInput(attrs={"type": "date"}),
        }

    def clean_name(self):
        return strip_tags(self.cleaned_data["name"]).strip()

    def clean_category(self):
        return strip_tags(self.cleaned_data["category"]).strip()

    def clean_image_url(self):
        url = self.cleaned_data.get("image_url", "").strip()
        if url and urlsplit(url).scheme not in ("http", "https"):
            raise ValidationError("Gunakan URL foto dengan awalan http:// atau https://.")
        return url

    def clean_purchase_date(self):
        return self.cleaned_data.get("purchase_date") or timezone.localdate()

    def clean_expiration_date(self):
        return self.cleaned_data.get("expiration_date") or timezone.localdate()
