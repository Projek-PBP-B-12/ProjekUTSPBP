from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from FoodItem.models import FoodItem
from Location.models import Location
from Location.services import distance_km
from userprofile.models import UserProfile

from .models import SharedPost
from .services import public_coordinates


class OfferBoardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="board_reader")
        cls.donor = get_user_model().objects.create_user(username="board_donor")
        cls.origin = Location.objects.create(
            owner=cls.user, area_name="Kampus", latitude="-6.360000", longitude="106.830000",
        )
        cls.profile = UserProfile.objects.create(user=cls.user, default_location=cls.origin)

    def setUp(self):
        self.client.force_login(self.user)
        self.url = reverse("sharedpost:list")

    def offer(self, name="Roti", latitude="-6.363000", owner=None, category="GRAIN", days=3):
        owner = owner or self.donor
        location = Location.objects.create(
            owner=owner, area_name="Beji", latitude=latitude, longitude="106.830000",
        )
        food = FoodItem.objects.create(
            owner=owner, name=name, category=category, status="OFFERED",
            purchase_date=timezone.localdate(), expiration_date=timezone.localdate() + timedelta(days=days),
        )
        return SharedPost.objects.create(food_item=food, location=location, description="Ambil di lobi kos sore hari.")

    def ids(self, response):
        return [post.pk for post in response.context["posts"]]

    def test_default_radius_and_nearest_sort_use_owned_default_location(self):
        near = self.offer("Dekat")
        middle = self.offer("Sedang", latitude="-6.372000")
        self.offer("Jauh", latitude="-6.395000")
        response = self.client.get(self.url)
        self.assertEqual(self.ids(response), [near.pk, middle.pk])
        self.assertEqual(response.context["origin"], self.origin)
        self.assertEqual(response.context["selected_radius"], "2")
        self.assertEqual(response.context["selected_sort"], "nearest")
        self.assertContains(response, 'name="sort"')
        self.assertNotContains(response, 'value="expiry"')
        self.assertContains(response, "334 m")

    def test_radius_and_all_areas(self):
        near = self.offer()
        middle = self.offer(latitude="-6.372000")
        far = self.offer(latitude="-6.395000")
        self.assertEqual(self.ids(self.client.get(self.url, {"radius": "1"})), [near.pk])
        response = self.client.get(self.url, {"radius": ""})
        self.assertEqual(self.ids(response), [near.pk, middle.pk, far.pk])
        self.assertEqual(response.context["total_count"], 3)

    def test_both_sorts_use_newest_then_id_for_equal_distances_or_timestamps(self):
        earlier = self.offer(days=5)
        sooner = self.offer(days=1)
        latest = self.offer(days=3)
        same_time = timezone.now()
        SharedPost.objects.all().update(created_at=same_time)
        for value in ["nearest", "newest"]:
            with self.subTest(sort=value):
                response = self.client.get(self.url, {"sort": value})
                self.assertEqual(self.ids(response), [latest.pk, sooner.pk, earlier.pk])
                self.assertEqual(response.context["selected_sort"], value)

    def test_nearest_and_newest_produce_different_orders(self):
        near = self.offer("Dekat", latitude="-6.361000")
        far = self.offer("Jauh", latitude="-6.372000")
        middle = self.offer("Sedang", latitude="-6.365000")
        self.assertEqual(self.ids(self.client.get(self.url, {"sort": "nearest"})), [near.pk, middle.pk, far.pk])
        self.assertEqual(self.ids(self.client.get(self.url, {"sort": "newest"})), [middle.pk, far.pk, near.pk])

    def test_equal_distances_prioritize_publication_time_before_id(self):
        newer = self.offer("Baru")
        older = self.offer("Lama")
        SharedPost.objects.filter(pk=older.pk).update(created_at=newer.created_at - timedelta(days=1))
        self.assertEqual(self.ids(self.client.get(self.url, {"sort": "nearest"})), [newer.pk, older.pk])

    def test_unsupported_sort_falls_back_to_newest(self):
        near = self.offer("Dekat", latitude="-6.361000")
        far = self.offer("Jauh", latitude="-6.372000")
        for value in ["expiry", "", "invalid", '<script>alert(1)</script>']:
            with self.subTest(sort=value):
                response = self.client.get(self.url, {"sort": value})
                self.assertEqual(self.ids(response), [far.pk, near.pk])
                self.assertEqual(response.context["selected_sort"], "newest")
                self.assertEqual(parse_qs(urlsplit(response.context["next_url"]).query)["sort"], ["newest"])

    def test_missing_origin_keeps_posts_and_offers_a_setup_link(self):
        self.profile.delete()
        near = self.offer()
        far = self.offer(latitude="-6.395000")
        response = self.client.get(self.url, {"radius": "1"})
        self.assertIsNone(response.context["origin"])
        self.assertEqual(set(self.ids(response)), {near.pk, far.pk})
        self.assertEqual(response.context["selected_radius"], "")
        self.assertEqual(response.context["selected_sort"], "newest")
        self.assertContains(response, "Atur lokasi bawaan")
        self.assertContains(response, 'name="radius" aria-label="Radius pencarian" disabled')
        self.assertEqual(response.context["posts"][0].distance_label, "Beji")

    def test_nearest_without_a_default_location_falls_back_to_newest(self):
        self.profile.delete()
        near = self.offer("Dekat")
        far = self.offer("Jauh", latitude="-6.395000")
        response = self.client.get(self.url, {"sort": "nearest"})
        self.assertEqual(self.ids(response), [far.pk, near.pk])
        self.assertEqual(response.context["selected_sort"], "newest")
        self.assertContains(response, '<option value="nearest" disabled>Terdekat</option>')
        self.assertContains(response, '<option value="newest" selected>Terbaru</option>')

    def test_foreign_default_location_is_not_used_or_disclosed(self):
        foreign = Location.objects.create(owner=self.donor, area_name="Titik pribadi", latitude=0, longitude=0)
        UserProfile.objects.filter(pk=self.profile.pk).update(default_location=foreign)
        self.offer()
        response = self.client.get(self.url)
        self.assertIsNone(response.context["origin"])
        self.assertEqual(response.context["selected_sort"], "newest")
        self.assertNotContains(response, "Titik pribadi")

    def test_category_values_still_follow_fooditem_and_combine_with_mine_and_search(self):
        target = self.offer("Roti sendiri", owner=self.user)
        self.offer("Roti donor")
        self.offer("Susu sendiri", owner=self.user, category="BEVERAGE")
        response = self.client.get(self.url, {"q": "roti", "category": "GRAIN", "mine": "1"})
        self.assertEqual(self.ids(response), [target.pk])
        self.assertEqual(response.context["all_count"], 2)
        self.assertEqual(response.context["total_count"], 1)
        self.assertEqual(
            response.context["categories"],
            list(FoodItem._meta.get_field("category").choices),
        )

    def test_category_labels_follow_model_in_filters_and_cards_after_htmx_filtering(self):
        choices = list(FoodItem._meta.get_field("category").choices)
        offers = {value: self.offer(category=value) for value, label in choices}
        for value, label in choices:
            for headers in [{}, {"HTTP_HX_REQUEST": "true"}]:
                with self.subTest(category=value, htmx=bool(headers)):
                    response = self.client.get(self.url, {"category": value}, **headers)
                    self.assertEqual(self.ids(response), [offers[value].pk])
                    self.assertEqual(response.context["posts"][0].category_label, label)
                    self.assertContains(response, f'<span class="category-pill">{label}</span>', html=True)
                    if not headers:
                        self.assertContains(
                            response,
                            f'<label><input type="radio" name="category" value="{value}" checked '
                            f'onchange="this.form.requestSubmit()"><span>{label}</span></label>',
                            html=True,
                        )

    def test_load_more_grows_six_at_a_time_without_duplicates(self):
        offers = [self.offer(f"Roti {index}") for index in range(14)]
        previous = []
        for page, shown in [(1, 6), (2, 12), (3, 14)]:
            response = self.client.get(self.url, {"page": page}, HTTP_HX_REQUEST="true")
            ids = self.ids(response)
            self.assertEqual(len(ids), shown)
            self.assertEqual(len(set(ids)), shown)
            self.assertEqual(ids[:len(previous)], previous)
            self.assertEqual(response.context["total_count"], 14)
            self.assertEqual(response.context["has_more"], page < 3)
            self.assertContains(response, 'hx-swap-oob="outerHTML"')
            self.assertNotContains(response, "<!DOCTYPE")
            previous = ids
        self.assertEqual(set(previous), {post.pk for post in offers})

    def test_next_link_preserves_all_filters_and_ordinary_navigation(self):
        for index in range(8):
            self.offer(f"Roti & susu {index}", owner=self.user)
        filters = {"q": "Roti & susu", "category": "GRAIN", "mine": "1", "radius": "5", "sort": "nearest"}
        response = self.client.get(self.url, filters)
        next_url = response.context["next_url"]
        parameters = parse_qs(urlsplit(next_url).query)
        for key, value in filters.items():
            self.assertEqual(parameters[key], [value])
        self.assertEqual(parameters["page"], ["2"])
        next_response = self.client.get(next_url)
        self.assertEqual(len(self.ids(next_response)), 8)
        self.assertTemplateUsed(next_response, "SharedPost/list.html")
        self.assertContains(next_response, '<option value="nearest" selected>Terdekat</option>')
        self.assertNotContains(next_response, "Lihat lebih banyak penawaran")

    def test_deletion_preserves_loaded_page_and_filters(self):
        offers = [self.offer(f"Roti {index}", owner=self.user) for index in range(14)]
        self.offer("Susu", owner=self.user, category="BEVERAGE")
        response = self.client.post(reverse("sharedpost:delete", args=[offers[0].pk]), {
            "q": "Roti", "category": "GRAIN", "mine": "1", "radius": "1", "page": "2", "sort": "nearest",
        }, HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page_number"], 2)
        self.assertEqual(response.context["total_count"], 13)
        self.assertEqual(len(self.ids(response)), 12)
        self.assertNotIn(offers[0].pk, self.ids(response))
        self.assertEqual(response.context["selected_sort"], "nearest")

    def test_completion_clamps_page_after_last_offer_is_removed(self):
        offers = [self.offer(f"Roti {index}", owner=self.user) for index in range(7)]
        response = self.client.post(reverse("sharedpost:complete", args=[offers[0].pk]), {
            "page": "2", "mine": "1", "sort": "newest",
        }, HTTP_HX_REQUEST="true")
        self.assertEqual(response.context["page_number"], 1)
        self.assertEqual(response.context["total_count"], 6)
        self.assertFalse(response.context["has_more"])
        self.assertEqual(response.context["selected_sort"], "newest")
        offers[0].refresh_from_db()
        self.assertFalse(offers[0].is_active)

    def test_distances_use_the_same_approximate_coordinates_as_the_map(self):
        post = self.offer(latitude="-6.361234")
        response = self.client.get(self.url)
        shown = response.context["posts"][0]
        latitude, longitude = public_coordinates(post.location)
        self.assertAlmostEqual(shown.distance_km, distance_km(self.origin.latitude, self.origin.longitude, latitude, longitude))
        self.assertNotContains(response, "-6.361234")

    def test_claim_opens_detail_without_mutating_food_or_offer(self):
        post = self.offer()
        response = self.client.get(self.url)
        self.assertContains(response, 'aria-label="Klaim Roti"')
        detail = self.client.get(reverse("sharedpost:detail", args=[post.pk]))
        self.assertContains(detail, "Hubungi donor")
        post.refresh_from_db()
        self.assertTrue(post.is_active)
        self.assertEqual(post.food_item.status, "OFFERED")

    def test_invalid_filters_and_page_values_are_handled(self):
        for index in range(8):
            self.offer(f"Roti {index}")
        for value in ["", "0", "-1", "wat", "9" * 100, "١", '<script>alert(1)</script>']:
            with self.subTest(page=value):
                response = self.client.get(self.url, {"page": value, "radius": "nan", "category": value})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context["page_number"], 1)
                self.assertEqual(len(self.ids(response)), 6)
                self.assertEqual(response.context["selected_radius"], "")
                self.assertEqual(response.context["selected_category"], "")
        response = self.client.get(self.url, {"page": "999999"})
        self.assertEqual(len(self.ids(response)), 8)
