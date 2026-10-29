from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST
from django.http import Http404, HttpResponse
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from FoodItem.models import FoodItem
from Location.models import Location
from .forms import SharedPostForm
from .models import SharedPost
from .services import get_board_context
from .decorators import limit_sharedpost_writes


@never_cache
@login_required
@require_http_methods(["GET", "HEAD"])
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
        and post.food_item.owner.is_active
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
            "map_url": (
                reverse("Location:map") + f"?post={post.pk}"
                if is_available and post.location.owner_id == post.food_item.owner_id else None
            ),
        },
    )


def _locked_post_and_food(user, pk, active_only=False):
    # Setiap alur inventori/penawaran mengunci makanan sebelum penawaran.
    owned = SharedPost.objects.filter(food_item__owner=user)
    if active_only:
        owned = owned.filter(is_active=True)
    food_id = get_object_or_404(owned, pk=pk).food_item_id
    food = get_object_or_404(FoodItem.objects.select_for_update(), pk=food_id, owner=user)
    post = get_object_or_404(owned.select_for_update(), pk=pk)
    return post, food


@login_required
@require_POST
@limit_sharedpost_writes
def complete_shared_post(request, pk):
    with transaction.atomic():
        post, food = _locked_post_and_food(request.user, pk, active_only=True)

        post.is_active = False
        post.save(update_fields=["is_active", "updated_at"])

        food.status = "CONSUMED"
        food.save(update_fields=["status", "updated_at"])

    if request.headers.get("HX-Request") == "true":
        response = shared_post_list(request)
        response["X-SharedPost-Action"] = "complete"
        return response

    return redirect("sharedpost:list")


@login_required
@require_POST
@limit_sharedpost_writes
def delete_shared_post(request, pk):
    with transaction.atomic():
        post, food = _locked_post_and_food(request.user, pk)

        if post.is_active and food.status == "OFFERED":
            food.status = "STORED"
            food.save(update_fields=["status", "updated_at"])

        post.delete()

    if request.headers.get("HX-Request") == "true":
        response = shared_post_list(request)
        response["X-SharedPost-Action"] = "delete"
        return response

    return redirect("sharedpost:list")


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
@limit_sharedpost_writes
def create_shared_post(request):
    if request.method == "POST":
        with transaction.atomic():
            # Kunci inventori selama proses pembuatan penawaran.
            # Evaluasi queryset agar kunci benar-benar diterapkan.
            list(
                FoodItem.objects.select_for_update().filter(
                    owner=request.user,
                ).order_by("pk")
            )

            form = SharedPostForm(
                request.POST,
                user=request.user,
            )

            if form.is_valid():
                form.instance.location = get_object_or_404(
                    Location.objects.select_for_update(),
                    pk=form.cleaned_data["location"].pk, owner=request.user,
                )
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
        selected_food = request.GET.get("food", "")
        if selected_food.isascii() and selected_food.isdigit() and len(selected_food) <= 18:
            if form.fields["food_item"].queryset.filter(pk=selected_food).exists():
                form.initial["food_item"] = int(selected_food)

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

@never_cache
@login_required
def shared_post_list(request):
    posts = SharedPost.objects.select_related(
        "food_item__owner",
        "location",
    ).filter(
        is_active=True,
        food_item__status="OFFERED",
        food_item__expiration_date__gte=timezone.localdate(),
        food_item__owner__is_active=True,
    )

    filters = request.GET if request.method == "GET" else request.POST
    context = get_board_context(posts, request.user, filters)
    context["is_htmx"] = request.headers.get("HX-Request") == "true"

    template = (
        "SharedPost/partials/post_list.html"
        if request.headers.get("HX-Request") == "true"
        else "SharedPost/list.html"
    )

    return render(
        request,
        template,
        context,
    )


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
@limit_sharedpost_writes
def update_shared_post(request, pk):
    is_htmx = request.headers.get("HX-Request") == "true"

    with transaction.atomic():
        post, food = _locked_post_and_food(request.user, pk, active_only=True)

        if request.method == "POST":
            form = SharedPostForm(
                request.POST,
                instance=post,
                user=request.user,
            )

            if form.is_valid():
                form.instance.location = get_object_or_404(
                    Location.objects.select_for_update(),
                    pk=form.cleaned_data["location"].pk, owner=request.user,
                )
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
