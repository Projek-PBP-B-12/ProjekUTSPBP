from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpRequest
from django.views.decorators.http import require_GET, require_POST
from django.db.models import ProtectedError
from .services import GeocodingError, geocode_address
from django.contrib.auth.decorators import login_required

from .forms import LocationForm
from .models import Location

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

#
# Lalu tempel kode di bawah ini di bagian paling bawah Location/views.py.

# TODO: ganti dengan data penawaran asli (SharedPost) setelah disepakati dengan Justin.
# Bentuk tiap item sengaja sama dengan kontrak JSON yang dibahas, supaya
# template dan JavaScript tidak perlu berubah saat sumber datanya diganti.
DUMMY_PINS = [
    {
        "id": 1,
        "title": "Roti gandum, masih utuh",
        "category": "Roti",
        "description": "Beli dua, satu belum dibuka. Ambil di lobi kos putri.",
        "photo_url": None,
        "area_name": "Kukusan",
        "latitude": "-6.366000",
        "longitude": "106.818200",
        "distance_km": 0.35,
        "detail_url": "#",
    },
    {
        "id": 2,
        "title": "Sayur sop siap dimasak",
        "category": "Sayuran",
        "description": "Wortel, kol, dan buncis. Sudah dicuci bersih.",
        "photo_url": None,
        "area_name": "Kukusan",
        "latitude": "-6.368900",
        "longitude": "106.821500",
        "distance_km": 0.8,
        "detail_url": "#",
    },
    {
        "id": 3,
        "title": "Susu kedelai 2 botol",
        "category": "Minuman",
        "description": "Masih tersegel dan selalu disimpan dingin.",
        "photo_url": None,
        "area_name": "Beji",
        "latitude": "-6.371500",
        "longitude": "106.817000",
        "distance_km": 1.2,
        "detail_url": "#",
    },
    {
        "id": 4,
        "title": "Nasi putih masih hangat",
        "category": "Nasi",
        "description": "Sisa nasi dari acara kecil, masih bersih dan layak.",
        "photo_url": None,
        "area_name": "Kukusan",
        "latitude": "-6.364200",
        "longitude": "106.822800",
        "distance_km": 0.5,
        "detail_url": "#",
    },
    {
        "id": 5,
        "title": "Apel merah 6 buah",
        "category": "Buah",
        "description": "Dibeli terlalu banyak, masih segar dan mulus semua.",
        "photo_url": None,
        "area_name": "Beji",
        "latitude": "-6.362500",
        "longitude": "106.814500",
        "distance_km": 0.95,
        "detail_url": "#",
    },
]


@login_required
def map_page(request):
    return render(request, "Location/map.html", {"pins": DUMMY_PINS})