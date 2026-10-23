from django.shortcuts import render

# Create your views here.
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render

from FoodItem.models import FoodItem
from .forms import SharedPostForm


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

                return redirect(
                    "sharedpost:create",
                )
    else:
        form = SharedPostForm(user=request.user)

    return render(
        request,
        "SharedPost/create.html",
        {"form": form},
    )