from urllib.parse import urlsplit

from django.contrib import messages
from django.contrib.auth import get_user_model, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError, RestrictedError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.utils.translation import override
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_safe
from django.views.decorators.debug import sensitive_post_parameters

from .forms import DeleteAccountForm, LoginForm, RegistrationForm, UserProfileForm
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


@never_cache
@login_required
@require_http_methods(["GET", "POST", "HEAD"])
@override("id")
def profile_edit(request):
    profile = UserProfile.objects.filter(user=request.user).first()
    if profile is None:
        profile = UserProfile(user=request.user)
    form = UserProfileForm(
        request.POST if request.method == "POST" else None, instance=profile
    )
    if request.method == "POST" and form.is_valid():
        UserProfile.objects.update_or_create(
            user=request.user, defaults=form.cleaned_data
        )
        messages.success(request, "Profil berhasil diperbarui.")
        return redirect("userprofile:profile")
    return render(request, "userprofile/profile_edit.html", {"form": form})


@never_cache
@login_required
@require_safe
def donor_contact(request, user_id):
    account = get_object_or_404(
        get_user_model().objects.filter(is_active=True).values(
            "username", "profile__whatsapp_number", "profile__line_id"
        ),
        pk=user_id,
    )
    contact = {
        "username": account["username"],
        "whatsapp_number": account["profile__whatsapp_number"] or "",
        "line_id": account["profile__line_id"] or "",
    }
    whatsapp_url = None
    if contact["whatsapp_number"]:
        try:
            UserProfile._meta.get_field("whatsapp_number").run_validators(
                contact["whatsapp_number"]
            )
        except ValidationError:
            pass
        else:
            whatsapp_url = f"https://wa.me/{contact['whatsapp_number']}"
    return render(request, "userprofile/donor_contact.html", {
        "contact": contact, "whatsapp_url": whatsapp_url,
    })


@never_cache
@login_required
@require_http_methods(["GET", "POST", "HEAD"])
@sensitive_post_parameters("password")
@override("id")
def delete_account(request):
    form = DeleteAccountForm(user=request.user)
    deleted = False
    if request.method == "POST":
        try:
            with transaction.atomic():
                account = get_object_or_404(
                    get_user_model().objects.select_for_update(),
                    pk=request.user.pk, is_active=True,
                )
                form = DeleteAccountForm(request.POST, user=account)
                if form.is_valid():
                    account.delete()
                    deleted = True
        except (ProtectedError, RestrictedError):
            form.add_error(
                None,
                "Akun belum dapat dihapus karena masih memiliki data terkait yang "
                "harus diselesaikan. Hubungi pengelola aplikasi.",
            )
        if deleted:
            logout(request)
            messages.success(request, "Akun dan profilmu berhasil dihapus.")
            return redirect("landing_page")
    return render(request, "userprofile/delete_account.html", {"form": form})
