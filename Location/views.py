from django.shortcuts import render,get_object_or_404
from django.http import JsonResponse, HttpRequest
from django.views.decorators.http import require_GET, require_POST
from django.db.models import ProtectedError
from .services import GeocodingError, geocode_address
from django.contrib.auth.decorators import login_required
from types import SimpleNamespace
from django.utils import timezone

from .forms import LocationForm
from .models import Location
from SharedPost.models import SharedPost
from SharedPost.services import get_map_pins

def auth_required():
    return JsonResponse({"message": "Authentication required."}, status=401)

def location_to_dict(location):
    return {
        "id": location.id,
        "fields": {
            "area_name": location.area_name,
            "latitude": str(location.latitude),
            "longitude": str(location.longitude)
        },
    }


@require_GET
def search_locations(request: HttpRequest):
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

# Berisi lokasi yang sudah disimpan user
def get_locations(request: HttpRequest):
    if not request.user.is_authenticated:
        return auth_required()

    locations = request.user.locations.all()
    location_id = request.GET.get("id", "")
    area_name = request.GET.get("area-name", "")

    if location_id:
        if not location_id.isdigit():
            return JsonResponse({"message": "Invalid id."}, status=400)
        locations = locations.filter(id=location_id)
    if area_name:
        locations = locations.filter(area_name__icontains=area_name)

    return JsonResponse([location_to_dict(location) for location in locations], safe=False)

@require_POST
def create_location(request):
    if not request.user.is_authenticated:
        return auth_required()
    
    form = LocationForm(request.POST)
    if not form.is_valid():
        return JsonResponse({"errors": form.errors.get_json_data()}, status=400)

    location = form.save(commit=False)
    location.owner = request.user
    location.save()
    return JsonResponse(location_to_dict(location), status=201)

@require_POST
def update_location(request: HttpRequest, pk):
    if not request.user.is_authenticated:
        return auth_required()
    
    location = get_object_or_404(Location, pk=pk, owner=request.user)
    form = LocationForm(request.POST, instance=location)
    if not form.is_valid():
        return JsonResponse({"errors": form.errors.get_json_data()}, status=400)
    form.save()
    return JsonResponse(location_to_dict(location), status=201)

@require_POST
def delete_location(request:HttpRequest, pk):
    if not request.user.is_authenticated:
        return auth_required()
    
    location = get_object_or_404(Location, pk=pk, owner=request.user)
    try:
        location.delete()
    except ProtectedError:
        return JsonResponse({"message": "Lokasi masih dipakai di penawaran"}, status=409)
    return JsonResponse({"message": "Location deleted."})

@login_required
def map_page(request: HttpRequest):
    posts = SharedPost.objects.filter(
        is_active=True,
        food_item__status="OFFERED",
        food_item__expiration_date__gte=timezone.localdate()
        )
    origin = None
    profile = getattr(request.user, "profile", None)
    if profile and profile.default_latitude is not None:
        origin = SimpleNamespace(
            latitude=profile.default_latitude,
            longitude=profile.default_longitude
        )
    pins = get_map_pins(posts, origin=origin)

    return render(request, "Location/map.html", {"pins": pins})