from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import F, ProtectedError, RestrictedError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from SharedPost.models import SharedPost
from SharedPost.services import get_map_pins
from userprofile.models import UserProfile

from .forms import LocationForm
from .models import Location
from .services import GeocodingError, geocode_address


LOCATION_IN_USE = (
    "Lokasi masih dipakai di penawaran. Tambahkan lokasi baru agar titik pengambilan "
    "pada penawaran yang sudah dibuat tidak ikut berubah."
)


def auth_required():
    return JsonResponse({"message": "Authentication required."}, status=401)


def location_to_dict(location):
    return {
        "id": location.id,
        "fields": {
            "area_name": location.area_name,
            "latitude": str(location.latitude),
            "longitude": str(location.longitude),
        },
    }


def _set_default(user, location):
    # Caller always retrieves the location with owner=user before entering here.
    UserProfile.objects.update_or_create(user=user, defaults={"default_location": location})


def _default_location_id(user):
    return UserProfile.objects.filter(user=user).values_list("default_location_id", flat=True).first()


@never_cache
@require_GET
def search_locations(request):
    if not request.user.is_authenticated:
        return auth_required()
    query = request.GET.get("q", "").strip()[:150]
    if len(query) < 3:
        return JsonResponse({"message": "Kata kunci minimal 3 karakter."}, status=400)
    try:
        results = geocode_address(query)
    except GeocodingError as exc:
        return JsonResponse({"message": str(exc)}, status=502)
    return JsonResponse(results, safe=False)


@never_cache
@require_GET
def get_locations(request):
    if not request.user.is_authenticated:
        return auth_required()
    locations = request.user.locations.all()
    location_id = request.GET.get("id", "")
    area_name = request.GET.get("area-name", "")
    if location_id:
        if not location_id.isascii() or not location_id.isdigit() or len(location_id) > 19 or int(location_id) > 2**63 - 1:
            return JsonResponse({"message": "Invalid id."}, status=400)
        locations = locations.filter(id=location_id)
    if area_name:
        locations = locations.filter(area_name__icontains=area_name)
    return JsonResponse([location_to_dict(location) for location in locations], safe=False)


@never_cache
@require_POST
def create_location(request):
    if not request.user.is_authenticated:
        return auth_required()
    form = LocationForm(request.POST)
    if not form.is_valid():
        return JsonResponse({"errors": form.errors.get_json_data()}, status=400)
    with transaction.atomic():
        location = form.save(commit=False)
        location.owner = request.user
        location.save()
        if form.cleaned_data["make_default"]:
            _set_default(request.user, location)
    return JsonResponse(location_to_dict(location), status=201)


@never_cache
@require_POST
def update_location(request, pk):
    if not request.user.is_authenticated:
        return auth_required()
    with transaction.atomic():
        location = get_object_or_404(Location.objects.select_for_update(), pk=pk, owner=request.user)
        if location.shared_posts.exists():
            return JsonResponse({"message": LOCATION_IN_USE}, status=409)
        form = LocationForm(request.POST, instance=location)
        if not form.is_valid():
            return JsonResponse({"errors": form.errors.get_json_data()}, status=400)
        form.save()
        if form.cleaned_data["make_default"]:
            _set_default(request.user, location)
    return JsonResponse(location_to_dict(location), status=201)


@never_cache
@require_POST
def delete_location(request, pk):
    if not request.user.is_authenticated:
        return auth_required()
    try:
        with transaction.atomic():
            location = get_object_or_404(Location.objects.select_for_update(), pk=pk, owner=request.user)
            location.delete()
    except (ProtectedError, RestrictedError):
        return JsonResponse({"message": LOCATION_IN_USE}, status=409)
    return JsonResponse({"message": "Location deleted."})


def _management_context(request, form, editing=None):
    locations = request.user.locations.prefetch_related("shared_posts")
    return {
        "locations": locations,
        "default_location_id": _default_location_id(request.user),
        "form": form,
        "editing": editing,
        "locked": editing is not None and editing.shared_posts.exists(),
    }


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def manage_locations(request):
    form = LocationForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            location = form.save(commit=False)
            location.owner = request.user
            location.save()
            if form.cleaned_data["make_default"]:
                _set_default(request.user, location)
        messages.success(request, "Lokasi berhasil ditambahkan.")
        return redirect("Location:manage")
    return render(request, "Location/manage.html", _management_context(request, form))


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def manage_edit(request, pk):
    with transaction.atomic():
        location = get_object_or_404(Location.objects.select_for_update(), pk=pk, owner=request.user)
        form = LocationForm(request.POST if request.method == "POST" else None, instance=location)
        locked = location.shared_posts.exists()
        if request.method == "POST":
            if locked:
                form.is_valid()
                form.add_error(None, LOCATION_IN_USE)
            elif form.is_valid():
                form.save()
                if form.cleaned_data["make_default"]:
                    _set_default(request.user, location)
                messages.success(request, "Lokasi berhasil diperbarui.")
                return redirect("Location:manage")
    return render(request, "Location/manage.html", _management_context(request, form, editing=location))


@never_cache
@login_required
@require_POST
def manage_delete(request, pk):
    try:
        with transaction.atomic():
            location = get_object_or_404(Location.objects.select_for_update(), pk=pk, owner=request.user)
            location.delete()
    except (ProtectedError, RestrictedError):
        messages.error(request, LOCATION_IN_USE)
    else:
        messages.success(request, "Lokasi berhasil dihapus.")
    return redirect("Location:manage")


@never_cache
@login_required
@require_POST
def set_default(request, pk):
    with transaction.atomic():
        location = get_object_or_404(Location.objects.select_for_update(), pk=pk, owner=request.user)
        _set_default(request.user, location)
    messages.success(request, f"{location.area_name} sekarang menjadi lokasi bawaan petamu.")
    return redirect("Location:manage")


@never_cache
@login_required
@require_GET
def map_page(request):
    default_location = Location.objects.filter(pk=_default_location_id(request.user), owner=request.user).first()
    center = {
        "latitude": str(default_location.latitude) if default_location else "-6.366000",
        "longitude": str(default_location.longitude) if default_location else "106.818000",
        "label": default_location.area_name if default_location else "Area Depok",
        "is_default": default_location is not None,
    }
    posts = SharedPost.objects.select_related("food_item", "location").filter(
        is_active=True,
        food_item__status="OFFERED",
        food_item__expiration_date__gte=timezone.localdate(),
        food_item__owner__is_active=True,
        location__owner_id=F("food_item__owner_id"),
    )
    pins = get_map_pins(posts, origin=default_location)
    selected_id = request.GET.get("post", "")
    selected = None
    if selected_id.isascii() and selected_id.isdigit() and len(selected_id) <= 19:
        selected = next((pin for pin in pins if pin["id"] == int(selected_id)), None)
    return render(request, "Location/map.html", {
        "pins": pins, "map_center": center,
        "selected_post_id": selected["id"] if selected else None,
        "selection_unavailable": bool(selected_id) and selected is None,
    })
