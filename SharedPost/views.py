from django.shortcuts import render

# Create your views here.
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST
from django.http import Http404, HttpResponse

from FoodItem.models import FoodItem
from .forms import SharedPostForm
from .models import SharedPost


@login_required
def shared_post_detail(request, pk):
    post = get_object_or_404(
        SharedPost.objects.select_related(
            "food_item__owner",
            "location",
        ),
        pk=pk,
    )

    is_owner = post.food_item.owner_id == request.user.id
    is_available = (
        post.is_active
        and post.food_item.status == "OFFERED"
        and not post.food_item.is_expired
    )

    if not is_owner and not is_available:
        raise Http404("Penawaran sudah tidak tersedia.")

    return render(
        request,
        "SharedPost/detail.html",
        {
            "post": post,
            "is_owner": is_owner,
            "is_available": is_available,
        },
    )


@login_required
@require_POST
def complete_shared_post(request, pk):
    with transaction.atomic():
        post = get_object_or_404(
            SharedPost.objects.select_for_update(),
            pk=pk,
            food_item__owner=request.user,
            is_active=True,
        )

        food = FoodItem.objects.select_for_update().get(
            pk=post.food_item_id,
        )

        post.is_active = False
        post.save(update_fields=["is_active", "updated_at"])

        food.status = "CONSUMED"
        food.save(update_fields=["status", "updated_at"])

    if request.headers.get("HX-Request") == "true":
        return shared_post_list(request)

    return redirect("sharedpost:list")


@login_required
@require_POST
def delete_shared_post(request, pk):
    with transaction.atomic():
        post = get_object_or_404(
            SharedPost.objects.select_for_update(),
            pk=pk,
            food_item__owner=request.user,
        )

        food = FoodItem.objects.select_for_update().get(
            pk=post.food_item_id,
        )

        if post.is_active and food.status == "OFFERED":
            food.status = "STORED"
            food.save(update_fields=["status", "updated_at"])

        post.delete()

    if request.headers.get("HX-Request") == "true":
        return shared_post_list(request)

    return redirect("sharedpost:list")


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

                if request.headers.get("HX-Request") == "true":
                    response = HttpResponse(
                        '<p role="status">Penawaran berhasil ditambahkan.</p>'
                    )
                    response["HX-Trigger"] = "postCreated"
                    return response

                return redirect("sharedpost:list")
    else:
        form = SharedPostForm(user=request.user)

    is_htmx = request.headers.get("HX-Request") == "true"
    template = (
        "SharedPost/partials/create_form.html"
        if is_htmx
        else "SharedPost/create.html"
    )

    return render(
        request,
        template,
        {"form": form, "is_htmx": is_htmx},
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

    filters = request.GET if request.method == "GET" else request.POST
    query = filters.get("q", "").strip()[:150]
    if query:
        posts = posts.filter(
            Q(food_item__name__icontains=query)
            | Q(location__area_name__icontains=query)
        )
    if filters.get("category"):
        posts = posts.filter(food_item__category=filters["category"])
    if filters.get("mine") == "1":
        posts = posts.filter(food_item__owner=request.user)

    template = (
        "SharedPost/partials/post_list.html"
        if request.headers.get("HX-Request") == "true"
        else "SharedPost/list.html"
    )

    return render(
        request,
        template,
        {"posts": posts},
    )


@login_required
def update_shared_post(request, pk):
    is_htmx = request.headers.get("HX-Request") == "true"

    with transaction.atomic():
        post = get_object_or_404(
            SharedPost.objects.select_for_update(),
            pk=pk,
            food_item__owner=request.user,
            is_active=True,
        )

        if request.method == "POST":
            form = SharedPostForm(
                request.POST,
                instance=post,
                user=request.user,
            )

            if form.is_valid():
                form.save()
                if is_htmx:
                    response = HttpResponse(
                        '<p role="status">Penawaran berhasil diperbarui.</p>'
                    )
                    response["HX-Trigger"] = "postUpdated"
                    return response

                return redirect("sharedpost:list")
        else:
            form = SharedPostForm(
                instance=post,
                user=request.user,
            )

    template = (
        "SharedPost/partials/update_form.html"
        if is_htmx
        else "SharedPost/update.html"
    )

    return render(
        request,
        template,
        {"form": form, "post": post, "is_htmx": is_htmx},
    )
