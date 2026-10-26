from urllib.parse import urlsplit

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.utils.decorators import method_decorator
from django.utils.translation import override
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_safe
from django.views.decorators.debug import sensitive_post_parameters

from .forms import LoginForm, RegistrationForm
from .models import UserProfile


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

@method_decorator(override("id"), name="dispatch")
class UserLoginView(LoginView):
    template_name = "userprofile/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True
    http_method_names = ["get", "post", "head", "options"]

    def get_success_url(self):
        destination = super().get_success_url()
        if urlsplit(destination).path == self.request.path:
            return self.get_default_redirect_url()
        return destination


class UserLogoutView(LogoutView):
    def get_success_url(self):
        return self.get_default_redirect_url()


@never_cache
@login_required
@require_safe
def profile_detail(request):
    profile = UserProfile.objects.filter(user=request.user).first()
    return render(request, "userprofile/profile.html", {"profile": profile})
