import requests
from django.core.cache import cache
import hashlib
import math
import os
from math import asin, cos, radians, sin, sqrt

NOMINATIM_URL = os.getenv("NOMINATIM_URL", "https://nominatim.openstreetmap.org/search")

USER_AGENT = "TitikLapar/1.0 (tugas PBP; https://github.com/Projek-PBP-B-12/ProjekUTSPBP)"

CACHE_SECONDS = 60 * 60 * 24

# Urutan pilihan nama area, dari yang paling spesifik.
AREA_KEYS = (
    "suburb",
    "village",
    "neighbourhood",
    "city_district",
    "city",
    "county",
    "state",
)


class GeocodingError(Exception):
    pass

def pick_area_name(address, fallback):
    for key in AREA_KEYS:
        if address.get(key):
            return address[key]
    return fallback


def geocode_address(query, limit=5):
    # Cari alamat/nama tempat lewat Nominatim, kembalikan daftar kandidat.
    query = " ".join(query.split())
    cache_key = "geocode:" + hashlib.sha1(f"{NOMINATIM_URL}:{limit}:{query.lower()}".encode()).hexdigest()
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    # Use a shared Django cache for deployments with more than one worker.
    if not cache.add("geocode:request-slot", True, timeout=1):
        raise GeocodingError("Tunggu sebentar sebelum mencari lokasi lagi.")

    try:
        response = requests.get(
            NOMINATIM_URL,
            params={
                "q": query,
                "format": "jsonv2",
                "addressdetails": 1,
                "limit": limit,
                "countrycodes": "id",
                "accept-language": "id",
            },
            headers={"User-Agent": USER_AGENT},
            timeout=5,
        )
        response.raise_for_status()
        raw_results = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise GeocodingError("Layanan pencarian lokasi sedang tidak tersedia.") from exc

    try:
        results = []
        for item in raw_results:
            latitude, longitude = float(item["lat"]), float(item["lon"])
            if not (math.isfinite(latitude) and math.isfinite(longitude) and abs(latitude) <= 90 and abs(longitude) <= 180):
                raise ValueError("Invalid coordinates")
            display_name = item["display_name"]
            if not isinstance(display_name, str):
                raise ValueError("Invalid location name")
            results.append({
                "area_name": pick_area_name(item.get("address", {}), item.get("name") or display_name)[:100],
                "display_name": display_name,
                "latitude": f"{latitude:.6f}",
                "longitude": f"{longitude:.6f}",
            })
    except (KeyError, ValueError, TypeError, AttributeError) as exc:
        raise GeocodingError("Hasil pencarian lokasi tidak valid. Coba lagi nanti.") from exc

    cache.set(cache_key, results, CACHE_SECONDS)
    return results

EARTH_RADIUS_KM = 6371.0088

def distance_km(lat1, lon1, lat2, lon2):
    # Jarak antara dua koordinat (rumus haversine), dalam kilometer
    lat1, lon1, lat2, lon2 = (radians(float(v)) for v in (lat1, lon1, lat2, lon2))
    a = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(min(1.0, max(0.0, a))))
