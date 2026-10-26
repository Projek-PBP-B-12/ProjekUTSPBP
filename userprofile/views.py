from django.shortcuts import redirect, render
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils.translation import override
from django.views.decorators.http import require_http_methods
from django.views.decorators.debug import sensitive_post_parameters

from .forms import RegistrationForm
from .models import UserProfile

# Create your views here.

@require_http_methods(["GET", "POST"])
@sensitive_post_parameters("password1", "password2")
@override("id")
def register(request):
    if request.user.is_authenticated:
        return redirect("landing_page")

    form = RegistrationForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                user = form.save()
                UserProfile.objects.create(user=user)
        except IntegrityError:
            if not get_user_model().objects.filter(username=form.cleaned_data["username"]).exists():
                raise
            form.add_error("username", "Nama pengguna sudah digunakan. Pilih nama lain.")
        else:
            messages.success(request, "Akun berhasil dibuat. Selamat bergabung di TitikLapar!")
            return redirect("landing_page")

    return render(request, "userprofile/register.html", {"form": form})
