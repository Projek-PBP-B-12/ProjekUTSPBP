import re
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import parse_qs, urlencode, urlsplit

from django.core.paginator import Paginator
from django.db.models import Q
from django.urls import reverse

from FoodItem.models import FoodItem
from Location.models import Location
from Location.services import distance_km


def normalize_photo_url(url):
    """Ubah link berbagi Google Drive menjadi URL thumbnail gambar."""
    if not url:
        return None

    try:
        parsed = urlsplit(url)
    except ValueError:
        return url

    if parsed.hostname != "drive.google.com" or parsed.scheme not in ("http", "https"):
        return url

    match = re.match(r"^/file/d/([\w-]+)(?:/|$)", parsed.path)
    file_id = match.group(1) if match else None
    if parsed.path in ("/open", "/uc"):
        file_id = parse_qs(parsed.query).get("id", [None])[0]

    if file_id and re.fullmatch(r"[\w-]+", file_id):
        return f"https://drive.google.com/thumbnail?id={file_id}&sz=w1000"
    return url


def public_coordinates(location):
    """Gunakan titik area yang sama untuk peta dan jarak publik."""
    return tuple(
        Decimal(str(coordinate)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
        for coordinate in (location.latitude, location.longitude)
    )


def get_map_pins(posts, origin=None):
    """Bentuk pin perkiraan dari queryset penawaran yang sudah difilter pemanggil.

    origin adalah objek beratribut latitude dan longitude, atau None.
    """
    pins = []
    for post in posts.select_related("food_item", "location"):
        location = post.location
        # Titik dan jarak publik memakai area yang sama, bukan koordinat rumah lengkap.
        latitude, longitude = public_coordinates(location)
        distance = None
        if origin is not None:
            distance = round(
                distance_km(
                    origin.latitude, origin.longitude,
                    latitude, longitude,
                ),
                2,
            )

        pins.append({
            "id": post.pk,
            "title": post.food_item.name,
            "category": post.food_item.get_category_display(),
            "description": post.description,
            "photo_url": normalize_photo_url(post.food_item.image_url),
            "area_name": location.area_name,
            "latitude": str(latitude),
            "longitude": str(longitude),
            "distance_km": distance,
            "detail_url": reverse("sharedpost:detail", args=[post.pk]),
        })
    return pins


CATEGORY_LABELS = {
    "GRAIN": "Roti & biji-bijian", "VEGETABLE": "Sayuran", "BEVERAGE": "Minuman",
    "FRUIT": "Buah", "MEAT": "Daging", "SEAFOOD": "Seafood", "DAIRY": "Susu & olahannya",
    "SNACK": "Camilan", "OTHER": "Lainnya",
}
RADIUS_OPTIONS = ("", "1", "2", "5", "10")
OFFERS_PER_PAGE = 6


def format_distance(kilometers):
    if kilometers < 1:
        return f"{round(kilometers * 1000)} m"
    return f"{kilometers:.1f}".replace(".", ",") + " km"


def get_board_context(posts, user, filters):
    """Filter jarak memakai koordinat perkiraan, lalu tampilkan bertahap per enam kartu."""
    choices = list(FoodItem._meta.get_field("category").choices)
    rank = {value: index for index, value in enumerate(CATEGORY_LABELS)}
    categories = [
        (value, CATEGORY_LABELS.get(value, label))
        for value, label in sorted(choices, key=lambda choice: rank.get(choice[0], len(rank)))
    ]
    labels = dict(categories)
    category = filters.get("category", "")
    if category not in labels:
        category = ""
    query = filters.get("q", "").strip()[:150]
    # Lokasi bawaan hanya boleh berasal dari lokasi milik akun sendiri.
    origin = Location.objects.filter(default_for_profiles__user=user, owner=user).first()
    radius = filters.get("radius", "2" if origin else "")
    if radius not in RADIUS_OPTIONS or not origin:
        radius = ""

    if query:
        posts = posts.filter(Q(food_item__name__icontains=query) | Q(location__area_name__icontains=query))
    if category:
        posts = posts.filter(food_item__category=category)
    posts = posts.order_by("-created_at", "-pk")

    offers = []
    for post in posts:
        post.distance_km = None
        if origin:
            latitude, longitude = public_coordinates(post.location)
            post.distance_km = distance_km(origin.latitude, origin.longitude, latitude, longitude)
            if radius and post.distance_km > float(radius):
                continue
        post.distance_label = format_distance(post.distance_km) if origin else post.location.area_name
        post.is_origin = bool(origin and origin.pk == post.location_id and post.food_item.owner_id == user.pk)
        post.category_label = labels.get(post.food_item.category, post.food_item.get_category_display())
        post.photo_url = normalize_photo_url(post.food_item.image_url)
        offers.append(post)

    all_count = len(offers)
    mine = filters.get("mine") == "1"
    if mine:
        offers = [post for post in offers if post.food_item.owner_id == user.pk]
    page_value = filters.get("page", "1")
    if not (page_value.isascii() and page_value.isdigit() and len(page_value) <= 6 and int(page_value) > 0):
        page_value = "1"
    page = Paginator(offers, OFFERS_PER_PAGE).get_page(page_value)
    shown = offers[:page.number * OFFERS_PER_PAGE]
    parameters = {
        "q": query, "category": category, "mine": "1" if mine else "0",
        "radius": radius, "page": page.number + 1,
    }
    return {
        "posts": shown, "total_count": len(offers), "all_count": all_count,
        "visible_count": len(shown), "page_number": page.number, "has_more": page.has_next(),
        "next_url": reverse("sharedpost:list") + "?" + urlencode(parameters),
        "categories": categories, "selected_category": category, "query": query, "mine": mine,
        "origin": origin, "selected_radius": radius,
        "radius_options": RADIUS_OPTIONS,
    }
