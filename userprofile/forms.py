from django.contrib.auth.forms import UserCreationForm, AuthenticationForm

class RegistrationForm(UserCreationForm):
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