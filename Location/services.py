import requests
from django.core.cache import cache
import hashlib

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

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
    cache_key = "geocode:" + hashlib.sha1(query.lower().encode()).hexdigest()
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

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

    results = [
        {
            "area_name": pick_area_name(
                item.get("address", {}),
                item.get("name") or item["display_name"],
            )[:100],
            "display_name": item["display_name"],
            # Model memakai 6 desimal, sedangkan Nominatim mengirim lebih panjang.
            "latitude": f"{float(item['lat']):.6f}",
            "longitude": f"{float(item['lon']):.6f}",
        }
        for item in raw_results
    ]

    cache.set(cache_key, results, CACHE_SECONDS)
    return results