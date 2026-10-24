from django.shortcuts import render
from datetime import datetime
from django.contrib import messages
from django.urls import reverse
from django.http import JsonResponse, HttpResponse, HttpRequest
from django.views.decorators.http import require_GET, require_POST
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .models import *
from .forms import *

# Create your views here.

global_context = {}

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
                "image_url": item.image_url,
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
def delete_food_item(request: HttpRequest, fooditem_id):
    if not request.user.is_authenticated:
        return JsonResponse(
            {"message": "Authentication required."},
            status=401,
        )

    fooditem = get_object_or_404(FoodItem, pk=fooditem_id)

    if fooditem.owner == request.user or request.user.is_superuser:
        fooditem.delete()
        return JsonResponse(
            {"message": "Makanan berhasil dihapus!"},
            status=200,
        )
    
    return JsonResponse(
        {"message": "Request not permitted."},
        status=403,
    )

@login_required
def add_food_item(request: HttpRequest):
    form = FoodItemForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        fooditem = form.save(commit=False)
        fooditem.owner = request.user
        fooditem.save()
        return redirect("landing_page")
    
    context = {
        "form" : form,
        "page_title": "Tambah Makanan",
        "submit_button_text": "Tambah Makanan",
        "post_form_url": reverse("FoodItem:add_food_item"),
        "cancel_button_url": reverse("landing_page")
    }
    return render(request, "form.html", global_context | context)

@login_required
def change_food_item(request: HttpRequest, fooditem_id):
    fooditem = get_object_or_404(FoodItem, pk=fooditem_id)
    form = FoodItemForm(request.POST or None, instance=fooditem)

    if fooditem.owner == request.user or request.user.is_superuser:

        if request.method == "POST" and form.is_valid():
            form.save()
            return redirect("landing_page")

        context = {
            "form" : form,
            "page_title": "Ubah Makanan",
            "submit_button_text": "Ubah Makanan",
            "post_form_url": reverse("FoodItem:change_food_item", kwargs={"fooditem_id": fooditem_id}),
            "cancel_button_url": reverse("landing_page")
        }
        return render(request, "form.html", global_context | context)

    return HttpResponse("Action not permitted.", status=403)