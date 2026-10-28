from django import forms
from .models import Location

class LocationForm(forms.ModelForm):
    make_default = forms.BooleanField(
        required=False,
        label="Jadikan lokasi bawaan untuk membuka peta",
        help_text="Pilihan ini tidak mengubah titik pengambilan penawaran yang sudah dibuat.",
    )

    class Meta:
        model = Location
        fields = ['area_name', 'latitude', 'longitude']
        labels = {
            "area_name": "Nama lokasi / area",
            "latitude": "Lintang (latitude)",
            "longitude": "Bujur (longitude)",
        }
        help_texts = {
            "area_name": "Contoh: Rumah — Kukusan, Kos — Beji, atau Kampus UI. Nama ini tampil jika dipilih untuk penawaran.",
            "latitude": "Antara -90 dan 90; maksimal 6 angka di belakang titik.",
            "longitude": "Antara -180 dan 180; maksimal 6 angka di belakang titik.",
        }
        widgets = {
            "area_name": forms.TextInput(attrs={"placeholder": "Contoh: Rumah — Kukusan", "autocomplete": "off"}),
            "latitude": forms.NumberInput(attrs={"step": "0.000001", "min": "-90", "max": "90", "inputmode": "decimal"}),
            "longitude": forms.NumberInput(attrs={"step": "0.000001", "min": "-180", "max": "180", "inputmode": "decimal"}),
        }
