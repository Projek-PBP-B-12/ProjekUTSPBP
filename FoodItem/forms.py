from django.forms import ModelForm, TextInput, Textarea, URLInput, NumberInput, DateInput
from django.utils.html import strip_tags

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
            "purchase_date": "Tanggal Beli",
            "expiration_date": "Tanggal Kedaluwarsa",
            "image_url": "URL Foto",
        }

        widgets = {
            "purchase_date": DateInput(attrs={"type": "date"}),
            "expiration_date": DateInput(attrs={"type": "date"}),
        }

    def clean_name(self):
        return strip_tags(self.cleaned_data["name"]).strip()

    def clean_category(self):
        return strip_tags(self.cleaned_data["category"]).strip()

    def clean_purchase_date(self):
        return self.cleaned_data.get("purchase_date") or timezone.localdate()

    def clean_expiration_date(self):
        return self.cleaned_data.get("expiration_date") or timezone.localdate()