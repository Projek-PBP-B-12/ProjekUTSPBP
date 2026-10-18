from django.shortcuts import render
from datetime import datetime

from django.http import JsonResponse, HttpRequest
from django.views.decorators.http import require_GET, require_POST

from .models import *

# Create your views here.

@require_GET
def get_food_items(request: HttpRequest):
    if not request.user.is_authenticated:
        return JsonResponse(
            {"message": "Authentication required."},
            status=401,
        )
    
    view_public = request.GET.get("view-public", "").lower() == "true"

    if view_public:
        items = FoodItem.objects.filter(status="OFFERED")
    else:
        items = request.user.food_items.all()

    # Filter berdasarkan setiap field
    item_id = request.GET.get("id", "")
    name = request.GET.get("name", "")
    category = request.GET.get("category", "")
    purchase_date = request.GET.get("purchase-date", "")
    expiration_date = request.GET.get("expiration-date", "")
    status = request.GET.get("status", "")
    created_at = request.GET.get("created-at", "")
    updated_at = request.GET.get("updated-at", "")
    expiration_state = request.GET.get("expiration-state", "")

    if item_id:
        items = items.filter(id=item_id)

    if name:
        items = items.filter(name__icontains=name)

    if category:
        items = items.filter(category=category)

    if purchase_date:
        items = items.filter(purchase_date=purchase_date)

    if expiration_date:
        items = items.filter(expiration_date=expiration_date)

    if status:
        items = items.filter(status=status)

    if created_at:
        items = items.filter(created_at__date=created_at)

    if updated_at:
        items = items.filter(updated_at__date=updated_at)

    if expiration_state:
        items = [
            item for item in items
            if item.expiration_state == expiration_state
        ]

    data = [
        {
            "id": item.id,
            "fields": {
                "owner_id": item.owner_id,
                "owner_username": item.owner.username,
                "name": item.name,
                "category": item.get_category_display(),
                "purchase_date": str(item.purchase_date),
                "expiration_date": str(item.expiration_date),
                "status": item.get_status_display(),
                "days_until_expiration": item.days_until_expiration,
                "is_expired": item.is_expired,
                "expiration_state": item.expiration_state,
                "created_at": item.created_at.isoformat(),
                "updated_at": item.updated_at.isoformat(),
            }
        }
        for item in items
    ]

    return JsonResponse(data, safe=False)

@require_POST
def create_food_item(request: HttpRequest):
    ...