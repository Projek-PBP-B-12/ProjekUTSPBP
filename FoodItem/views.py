from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Prefetch
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from SharedPost.models import SharedPost
from notification.views import generate_food_reminders, send_pending_reminder_emails
from .forms import FoodItemForm
from .models import FoodItem, FOOD_STATUSES


@never_cache
@login_required
@require_GET
def list_food_items(request):
    items = request.user.food_items.prefetch_related(Prefetch(
        "shared_posts", queryset=SharedPost.objects.filter(is_active=True),
        to_attr="active_posts",
    ))
    query = request.GET.get("q", "").strip()[:150]
    status = request.GET.get("status", "")
    if query:
        items = items.filter(name__icontains=query)
    if status in dict(FOOD_STATUSES):
        items = items.filter(status=status)
    return render(request, "FoodItem/makananku.html", {
        "items": items, "query": query, "selected_status": status,
    })


@never_cache
@require_GET
def get_food_items(request):
    if not request.user.is_authenticated:
        return JsonResponse({"message": "Authentication required."}, status=401)
    if request.GET.get("view-public", "").lower() == "true":
        items = FoodItem.objects.filter(
            status="OFFERED", shared_posts__is_active=True,
            expiration_date__gte=timezone.localdate(), owner__is_active=True,
        ).exclude(owner=request.user).distinct()
    else:
        items = request.user.food_items.all()
    items = items.select_related("owner")
    try:
        if request.GET.get("id"):
            item_id = int(request.GET["id"])
            if not 0 < item_id <= 9223372036854775807:
                raise ValueError
            items = items.filter(id=item_id)
        if request.GET.get("name"):
            items = items.filter(name__icontains=request.GET["name"][:150])
        for field in ("category", "status"):
            if request.GET.get(field):
                items = items.filter(**{field: request.GET[field].upper()})
        for key, field in (
            ("purchase-date", "purchase_date"), ("expiration-date", "expiration_date"),
            ("created-at", "created_at__date"), ("updated-at", "updated_at__date"),
        ):
            if request.GET.get(key):
                value = parse_date(request.GET[key])
                if value is None:
                    raise ValueError
                items = items.filter(**{field: value})
    except (ValueError, ValidationError):
        return JsonResponse({"message": "Filter ID atau tanggal tidak valid."}, status=400)
    if request.GET.get("expiration-state"):
        items = [item for item in items if item.expiration_state == request.GET["expiration-state"].upper()]
    return JsonResponse([
        {"id": item.id, "fields": {
            "owner_id": item.owner_id, "owner_username": item.owner.username,
            "name": item.name, "category": item.get_category_display(),
            "purchase_date": str(item.purchase_date), "expiration_date": str(item.expiration_date),
            "status": item.status, "image_url": item.image_url,
            "days_until_expiration": item.days_until_expiration,
            "is_expired": item.is_expired, "expiration_state": item.expiration_state,
            "created_at": item.created_at.isoformat(), "updated_at": item.updated_at.isoformat(),
        }} for item in items
    ], safe=False)


def _can_manage(user, food):
    return food.owner_id == user.pk or user.is_superuser


def _schedule_food_reminders(food):
    # Kirim hanya setelah data tersimpan; kegagalan email tidak membatalkan makanan.
    def process_saved_food():
        generate_food_reminders(recipient=food.owner, food_item=food)
        send_pending_reminder_emails(food_item=food)

    transaction.on_commit(process_saved_food, robust=True)


@require_POST
def delete_food_item(request, fooditem_id):
    if not request.user.is_authenticated:
        return JsonResponse({"message": "Authentication required."}, status=401)
    with transaction.atomic():
        food = get_object_or_404(FoodItem.objects.select_for_update(), pk=fooditem_id)
        if not _can_manage(request.user, food):
            return JsonResponse({"message": "Request not permitted."}, status=403)
        food.delete()
    return JsonResponse({"message": "Makanan berhasil dihapus!"})


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def add_food_item(request):
    form = FoodItemForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            food = form.save(commit=False)
            food.owner = request.user
            food.save()
            _schedule_food_reminders(food)
        messages.success(request, "Makanan berhasil ditambahkan.")
        return redirect("FoodItem:list_food_items")
    return render(request, "FoodItem/form.html", {
        "form": form, "page_title": "Tambah Makanan", "submit_button_text": "Tambah Makanan",
        "post_form_url": reverse("FoodItem:add_food_item"),
        "cancel_button_url": reverse("FoodItem:list_food_items"),
    })


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def change_food_item(request, fooditem_id):
    with transaction.atomic():
        food = get_object_or_404(FoodItem.objects.select_for_update(), pk=fooditem_id)
        if not _can_manage(request.user, food):
            return HttpResponse("Action not permitted.", status=403)
        was_expired = food.is_expired
        form = FoodItemForm(request.POST if request.method == "POST" else None, instance=food)
        if request.method == "POST" and form.is_valid():
            food = form.save()
            # Penawaran ditutup saat kedaluwarsa, tidak hidup kembali saat tanggal diedit.
            if was_expired or food.is_expired:
                food.shared_posts.filter(is_active=True).update(is_active=False, updated_at=timezone.now())
                if food.status == "OFFERED":
                    food.status = "STORED"
                    food.save(update_fields=["status", "updated_at"])
            _schedule_food_reminders(food)
            messages.success(request, "Informasi makanan berhasil diperbarui.")
            return redirect("FoodItem:list_food_items")
    return render(request, "FoodItem/form.html", {
        "form": form, "page_title": "Ubah Makanan", "submit_button_text": "Ubah Makanan",
        "post_form_url": reverse("FoodItem:change_food_item", args=[fooditem_id]),
        "cancel_button_url": reverse("FoodItem:list_food_items"),
    })


def _change_status(user, fooditem_id, status):
    with transaction.atomic():
        food = get_object_or_404(FoodItem.objects.select_for_update(), pk=fooditem_id)
        if not _can_manage(user, food):
            return {"message": "Request not permitted."}, 403
        if status == "OFFERED":
            if food.is_expired or not food.shared_posts.filter(is_active=True).exists():
                return {
                    "message": "Buat penawaran dan pilih lokasi pengambilan terlebih dahulu.",
                    "create_url": reverse("sharedpost:create") + f"?food={food.pk}",
                }, 409
        else:
            food.shared_posts.filter(is_active=True).update(is_active=False, updated_at=timezone.now())
        food.status = status
        food.save(update_fields=["status", "updated_at"])
    return {"message": "Status makanan berhasil diperbarui."}, 200


def _status_api(request, fooditem_id, status):
    if not request.user.is_authenticated:
        return JsonResponse({"message": "Authentication required."}, status=401)
    data, code = _change_status(request.user, fooditem_id, status)
    return JsonResponse(data, status=code)


@require_POST
def make_food_item_status_stored(request, fooditem_id):
    return _status_api(request, fooditem_id, "STORED")


@require_POST
def make_food_item_status_consumed(request, fooditem_id):
    return _status_api(request, fooditem_id, "CONSUMED")


@require_POST
def make_food_item_status_offered(request, fooditem_id):
    return _status_api(request, fooditem_id, "OFFERED")


@login_required
@require_POST
def change_status(request, fooditem_id):
    status = request.POST.get("status")
    if status not in ("STORED", "CONSUMED"):
        return HttpResponse("Status tidak valid.", status=400)
    data, code = _change_status(request.user, fooditem_id, status)
    if code != 200:
        return HttpResponse(data["message"], status=code)
    messages.success(request, data["message"])
    return redirect("FoodItem:list_food_items")


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def delete_food_page(request, fooditem_id):
    food = get_object_or_404(FoodItem, pk=fooditem_id, owner=request.user)
    if request.method == "POST":
        response = delete_food_item(request, fooditem_id)
        if response.status_code != 200:
            return response
        messages.success(request, "Makanan dan penawarannya berhasil dihapus.")
        return redirect("FoodItem:list_food_items")
    return render(request, "FoodItem/delete.html", {"food": food})
