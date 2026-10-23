from django.shortcuts import render

# Create your views here.
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone

from FoodItem.models import FoodItem
from .forms import SharedPostForm
from .models import SharedPost


@login_required
def create_shared_post(request):
    if request.method == "POST":
        with transaction.atomic():
            # Kunci inventori selama proses pembuatan penawaran.
            # Evaluasi queryset agar kunci benar-benar diterapkan.
            list(
                FoodItem.objects.select_for_update().filter(
                    owner=request.user,
                )
            )

            form = SharedPostForm(
                request.POST,
                user=request.user,
            )

            if form.is_valid():
                post = form.save()

                food = post.food_item
                food.status = "OFFERED"
                food.save(update_fields=["status", "updated_at"])

                return redirect("sharedpost:list")
    else:
        form = SharedPostForm(user=request.user)

    return render(
        request,
        "SharedPost/create.html",
        {"form": form},
    )

@login_required
def shared_post_list(request):
    posts = SharedPost.objects.select_related(
        "food_item__owner",
        "location",
    ).filter(
        is_active=True,
        food_item__status="OFFERED",
        food_item__expiration_date__gte=timezone.localdate(),
    )

    return render(
        request,
        "SharedPost/list.html",
        {"posts": posts},
    )
