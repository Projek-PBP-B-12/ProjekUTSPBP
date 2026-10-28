from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.hashers import check_password
from django.views.decorators.debug import sensitive_variables

from Location.models import Location
from .models import UserProfile


class RegistrationForm(UserCreationForm):
    """Pakai validasi dan hashing password bawaan Django."""

    email = forms.EmailField(
        label="Email",
        max_length=254,
        help_text="Pengingat kedaluwarsa dikirim ke email ini. Tidak ditampilkan kepada donor atau penerima.",
        widget=forms.EmailInput(attrs={"autocomplete": "email", "autocapitalize": "none"}),
    )

    class Meta(UserCreationForm.Meta):
        fields = ("username", "email")

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

    email = forms.EmailField(
        label="Email pengingat",
        max_length=254,
        help_text="Gunakan alamat email milikmu yang aktif. Email hanya terlihat olehmu dan tidak menjadi kontak berbagi.",
        widget=forms.EmailInput(attrs={"autocomplete": "email", "autocapitalize": "none"}),
    )

    class Meta:
        model = UserProfile
        fields = (
            "whatsapp_number",
            "line_id",
            "default_location",
        )
        labels = {
            "whatsapp_number": "Nomor WhatsApp",
            "line_id": "ID Line",
            "default_location": "Lokasi bawaan peta",
        }
        help_texts = {
            "whatsapp_number": "Gunakan 8–15 digit dengan kode negara, misalnya 6281234567890. Tanpa + atau spasi.",
            "line_id": "Masukkan ID Line, bukan nama tampilan. Maksimal 100 karakter.",
            "default_location": "Peta langsung dibuka di lokasi ini. Lokasi pengambilan tetap dipilih pada setiap penawaran makanan.",
        }
        widgets = {
            "whatsapp_number": forms.TextInput(attrs={
                "inputmode": "tel", "autocomplete": "tel", "placeholder": "6281234567890",
            }),
            "line_id": forms.TextInput(attrs={"autocapitalize": "none", "spellcheck": "false"}),
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].initial = user.email
        self.initial["email"] = user.email
        self.fields["default_location"].queryset = Location.objects.filter(
            owner=user
        ).order_by("area_name", "pk")
        self.fields["default_location"].empty_label = "Belum memilih lokasi bawaan"


class DeleteAccountForm(forms.Form):
    password = forms.CharField(
        label="Kata sandi saat ini",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
        error_messages={"required": "Masukkan kata sandi saat ini."},
    )
    confirm = forms.BooleanField(
        label="Saya memahami bahwa akun, profil, makanan, penawaran, lokasi, dan notifikasi saya akan dihapus permanen.",
        error_messages={"required": "Centang konfirmasi sebelum menghapus akun."},
    )

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    @sensitive_variables("password")
    def clean_password(self):
        password = self.cleaned_data["password"]
        if not check_password(password, self.user.password):
            raise forms.ValidationError("Kata sandi tidak sesuai.", code="incorrect_password")
        return password
