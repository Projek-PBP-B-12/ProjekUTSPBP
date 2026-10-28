import re
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import parse_qs, urlsplit

from django.urls import reverse

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


def get_map_pins(posts, origin=None):
    """Bentuk pin perkiraan dari queryset penawaran yang sudah difilter pemanggil.

    origin adalah objek beratribut latitude dan longitude, atau None.
    """
    pins = []
    for post in posts.select_related("food_item", "location"):
        location = post.location
        # Titik dan jarak publik memakai area yang sama, bukan koordinat rumah lengkap.
        latitude = location.latitude.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
        longitude = location.longitude.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
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
