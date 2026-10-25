from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpRequest
from django.views.decorators.http import require_GET, require_POST

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
def delete_location(request, pk):
    if not request.user.is_authenticated:
        return auth_required()
    
    location = get_object_or_404(Location, pk=pk, owner=request.user)
    location.delete()
    return JsonResponse({"message": "Location deleted."})