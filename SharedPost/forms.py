from django import forms
from django.db.models import Q
from django.utils import timezone

from FoodItem.models import FoodItem
from Location.models import Location
from .models import SharedPost


class SharedPostForm(forms.ModelForm):
    class Meta:
        model = SharedPost
        fields = ["food_item", "location", "description"]

        labels = {
            "food_item": "Makanan yang dibagikan",
            "location": "Lokasi pengambilan",
            "description": "Petunjuk pengambilan",
        }

        widgets = {
            "description": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": "Jelaskan waktu dan cara pengambilan.",
                    "minlength": 10,
                    "maxlength": 1000,
                }
            ),
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)

        available_foods = FoodItem.objects.filter(
            owner=user,
            status="STORED",
            expiration_date__gte=timezone.localdate(),
        ).exclude(
            shared_posts__is_active=True,
        )

        if self.instance.pk:
            # Saat edit, makanan tidak boleh diganti.
            # Tetap batasi pilihan ke makanan milik pengguna.
            available_foods = FoodItem.objects.filter(
                Q(pk__in=available_foods.values("pk"))
                | Q(pk=self.instance.food_item_id),
                owner=user,
            )
            self.fields["food_item"].disabled = True

        self.fields["food_item"].queryset = available_foods
        self.fields["location"].queryset = Location.objects.filter(
            owner=user,
        )

        self.fields["food_item"].empty_label = "Pilih makanan"
        self.fields["location"].empty_label = "Pilih lokasi"
        self.fields["location"].help_text = (
            "Pilih titik pengambilan secara sengaja, termasuk Rumah jika diinginkan. "
            "Nama lokasi dan area perkiraannya akan terlihat oleh pengguna lain pada penawaran. "
            "Lokasi bawaan profil hanya digunakan untuk memusatkan peta."
        )

    def clean_description(self):
        description = self.cleaned_data["description"].strip()

        if len(description) < 10:
            raise forms.ValidationError(
                "Petunjuk pengambilan minimal 10 karakter."
            )

        return description
