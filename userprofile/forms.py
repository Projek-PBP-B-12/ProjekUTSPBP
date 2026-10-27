from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import UserProfile


class RegistrationForm(UserCreationForm):
    """Pakai validasi dan hashing password bawaan Django."""

    class Meta(UserCreationForm.Meta):
        fields = ("username",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Nama pengguna"
        self.fields["username"].help_text = (
            "Maksimal 150 karakter. Gunakan huruf, angka, atau simbol @ . + - _."
        )
        self.fields["password1"].label = "Kata sandi"
        self.fields["password2"].label = "Ulangi kata sandi"
        self.fields["password2"].help_text = "Masukkan kata sandi yang sama untuk konfirmasi."
        self.fields["username"].widget.attrs.update(
            {"autocomplete": "username", "autocapitalize": "none", "spellcheck": "false"}
        )


class LoginForm(AuthenticationForm):
    """Autentikasi tetap dikerjakan Django; di sini hanya menyesuaikan tampilan."""

    error_messages = {
        "invalid_login": "Nama pengguna atau kata sandi tidak sesuai.",
        "inactive": "Akun ini tidak dapat digunakan untuk masuk.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Nama pengguna"
        self.fields["username"].widget.attrs.update(
            {"autocomplete": "username", "autocapitalize": "none", "spellcheck": "false"}
        )
        self.fields["password"].label = "Kata sandi"


class UserProfileForm(forms.ModelForm):
    """Daftar field eksplisit menjaga identitas dan hak akses di luar form."""

    class Meta:
        model = UserProfile
        fields = (
            "whatsapp_number",
            "line_id",
            "default_latitude",
            "default_longitude",
        )
        labels = {
            "whatsapp_number": "Nomor WhatsApp",
            "line_id": "ID Line",
            "default_latitude": "Lintang (latitude)",
            "default_longitude": "Bujur (longitude)",
        }
        help_texts = {
            "whatsapp_number": "Gunakan 8–15 digit dengan kode negara, misalnya 6281234567890. Tanpa + atau spasi.",
            "line_id": "Masukkan ID Line, bukan nama tampilan. Maksimal 100 karakter.",
            "default_latitude": "Rentang -90 sampai 90. Gunakan titik desimal, maksimal 6 angka di belakang titik.",
            "default_longitude": "Rentang -180 sampai 180. Isi bersama lintang, atau kosongkan keduanya.",
        }
        widgets = {
            "whatsapp_number": forms.TextInput(attrs={
                "inputmode": "tel", "autocomplete": "tel", "placeholder": "6281234567890",
            }),
            "line_id": forms.TextInput(attrs={"autocapitalize": "none", "spellcheck": "false"}),
            "default_latitude": forms.NumberInput(attrs={
                "min": "-90", "max": "90", "step": "0.000001", "placeholder": "Contoh: -6.360000",
            }),
            "default_longitude": forms.NumberInput(attrs={
                "min": "-180", "max": "180", "step": "0.000001", "placeholder": "Contoh: 106.820000",
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        coordinates = ("default_latitude", "default_longitude")
        if all(field in cleaned_data for field in coordinates):
            latitude, longitude = (cleaned_data[field] for field in coordinates)
            if (latitude is None) != (longitude is None):
                for field in coordinates:
                    self.add_error(
                        field, "Isi lintang dan bujur bersama, atau kosongkan keduanya."
                    )
        return cleaned_data