from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models.deletion import RestrictedError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from FoodItem.models import FoodItem
from Location.models import Location
from .models import SharedPost
from .forms import SharedPostForm


class SharedPostTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(
            username="donor_test",
        )

        cls.location = Location.objects.create(
            owner=cls.owner,
            area_name="Beji",
            latitude="-6.360000",
            longitude="106.830000",
        )

        cls.food = FoodItem.objects.create(
            owner=cls.owner,
            name="Roti gandum",
            category="GRAIN",
            purchase_date=timezone.localdate(),
            expiration_date=timezone.localdate() + timedelta(days=3),
            status="STORED",
        )

    def test_owner_can_create_post(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("sharedpost:create"),
            {
                "food_item": self.food.pk,
                "location": self.location.pk,
                "description": "Ambil di lobi kos pukul lima sore.",
            },
        )

        self.assertRedirects(
            response,
            reverse("sharedpost:list"),
            fetch_redirect_response=False,
        )

        self.assertEqual(SharedPost.objects.count(), 1)

        post = SharedPost.objects.get()
        self.assertEqual(post.food_item_id, self.food.pk)
        self.assertEqual(post.location_id, self.location.pk)
        self.assertEqual(
            post.description,
            "Ambil di lobi kos pukul lima sore.",
        )
        self.assertTrue(post.is_active)

        self.food.refresh_from_db()
        self.assertEqual(self.food.status, "OFFERED")

    def test_other_user_cannot_offer_owners_food(self):
        other_user = get_user_model().objects.create_user(
            username="other_user_test",
        )
        other_location = Location.objects.create(
            owner=other_user,
            area_name="Depok",
            latitude="-6.370000",
            longitude="106.840000",
        )
        self.client.force_login(other_user)

        response = self.client.post(
            reverse("sharedpost:create"),
            {
                "food_item": self.food.pk,
                "location": other_location.pk,
                "description": "Ambil di lobi kos pukul lima sore.",
            },
        )

        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertIn("food_item", form.errors)
        self.assertNotIn("location", form.errors)
        self.assertEqual(SharedPost.objects.count(), 0)

        self.food.refresh_from_db()
        self.assertEqual(self.food.status, "STORED")

    def test_other_user_cannot_delete_post(self):
        post = SharedPost.objects.create(
            food_item=self.food,
            location=self.location,
            description="Ambil di lobi kos pukul lima sore.",
        )
        self.food.status = "OFFERED"
        self.food.save(update_fields=["status"])

        other_user = get_user_model().objects.create_user(
            username="other_deleter_test",
        )
        self.client.force_login(other_user)

        response = self.client.post(
            reverse("sharedpost:delete", args=[post.pk]),
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(
            SharedPost.objects.filter(pk=post.pk).exists()
        )

        self.food.refresh_from_db()
        self.assertEqual(self.food.status, "OFFERED")

    def test_other_user_cannot_edit_post(self):
        post = SharedPost.objects.create(
            food_item=self.food,
            location=self.location,
            description="Ambil di lobi kos pukul lima sore.",
        )
        self.food.status = "OFFERED"
        self.food.save(update_fields=["status"])

        other_user = get_user_model().objects.create_user(
            username="other_editor_test",
        )
        self.client.force_login(other_user)

        url = reverse("sharedpost:update", args=[post.pk])

        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

        response = self.client.post(
            url,
            {
                "food_item": self.food.pk,
                "location": self.location.pk,
                "description": "Petunjuk diubah oleh pengguna lain.",
            },
        )
        self.assertEqual(response.status_code, 404)

        post.refresh_from_db()
        self.assertEqual(
            post.description,
            "Ambil di lobi kos pukul lima sore.",
        )
        self.assertEqual(post.location_id, self.location.pk)

        self.food.refresh_from_db()
        self.assertEqual(self.food.status, "OFFERED")


    def make_post(self, **overrides):
        self.food.status = "OFFERED"
        self.food.save(update_fields=["status"])
        return SharedPost.objects.create(
            food_item=self.food,
            location=self.location,
            description="Ambil di lobi kos pukul lima sore.",
            **overrides,
        )

    def payload(self, **overrides):
        return {
            "food_item": self.food.pk,
            "location": self.location.pk,
            "description": "Ambil di lobi kos pukul lima sore.",
            **overrides,
        }

    def make_other_user(self):
        return get_user_model().objects.create_user(username="visitor_test")

    def test_anonymous_requests_require_login(self):
        post = self.make_post()
        targets = [
            ("list", [], "get"), ("create", [], "get"),
            ("create", [], "post"), ("detail", [post.pk], "get"),
            ("update", [post.pk], "get"), ("update", [post.pk], "post"),
            ("delete", [post.pk], "post"), ("complete", [post.pk], "post"),
        ]
        for name, args, method in targets:
            with self.subTest(name=name, method=method):
                response = getattr(self.client, method)(reverse(f"sharedpost:{name}", args=args))
                self.assertEqual(response.status_code, 302)
                self.assertIn("next=", response.url)
        self.assertTrue(SharedPost.objects.filter(pk=post.pk, is_active=True).exists())
        self.food.refresh_from_db()
        self.assertEqual(self.food.status, "OFFERED")

    def test_create_form_regular_and_htmx(self):
        self.client.force_login(self.owner)
        for is_htmx in [False, True]:
            with self.subTest(htmx=is_htmx):
                headers = {"HTTP_HX_REQUEST": "true"} if is_htmx else {}
                response = self.client.get(reverse("sharedpost:create"), **headers)
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "SharedPost/partials/create_form.html")
                if is_htmx:
                    self.assertNotContains(response, "<!doctype")
                    self.assertContains(response, 'hx-post=')
                else:
                    self.assertTemplateUsed(response, "SharedPost/create.html")
                self.assertFalse(response.context["form"].is_bound)

    def test_create_htmx_returns_success_event(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse("sharedpost:create"), self.payload(), HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["HX-Trigger"], "postCreated")
        self.assertNotIn("Location", response)
        self.assertEqual(SharedPost.objects.get().food_item_id, self.food.pk)
        self.food.refresh_from_db()
        self.assertEqual(self.food.status, "OFFERED")

    def test_description_boundaries_and_whitespace(self):
        for value in ["", "   ", "123456789", "x" * 1001]:
            with self.subTest(description_length=len(value)):
                form = SharedPostForm(self.payload(description=value), user=self.owner)
                self.assertFalse(form.is_valid())
                self.assertIn("description", form.errors)
        for value in ["1234567890", "x" * 1000, "   Petunjuk pengambilan valid.   "]:
            with self.subTest(valid_length=len(value)):
                form = SharedPostForm(self.payload(description=value), user=self.owner)
                self.assertTrue(form.is_valid(), form.errors)
                self.assertEqual(form.cleaned_data["description"], value.strip())

    def test_invalid_create_regular_and_htmx_keeps_data_unchanged(self):
        self.client.force_login(self.owner)
        for is_htmx in [False, True]:
            with self.subTest(htmx=is_htmx):
                headers = {"HTTP_HX_REQUEST": "true"} if is_htmx else {}
                response = self.client.post(reverse("sharedpost:create"), self.payload(description="pendek"), **headers)
                self.assertEqual(response.status_code, 200)
                self.assertIn("description", response.context["form"].errors)
                self.assertContains(response, "minimal 10 karakter")
        self.assertFalse(SharedPost.objects.exists())
        self.food.refresh_from_db()
        self.assertEqual(self.food.status, "STORED")

    def test_required_and_nonexistent_choices_are_rejected(self):
        self.client.force_login(self.owner)
        for data in [{}, self.payload(food_item=999999), self.payload(location=999999)]:
            with self.subTest(data=data):
                response = self.client.post(reverse("sharedpost:create"), data)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors)
        self.assertFalse(SharedPost.objects.exists())

    def test_foreign_location_is_rejected(self):
        other = self.make_other_user()
        foreign_location = Location.objects.create(owner=other, area_name="Lokasi lain", latitude="-6.36", longitude="106.83")
        self.client.force_login(self.owner)
        response = self.client.post(reverse("sharedpost:create"), self.payload(location=foreign_location.pk))
        self.assertIn("location", response.context["form"].errors)
        self.assertNotIn("food_item", response.context["form"].errors)
        self.assertFalse(SharedPost.objects.exists())

    def test_ineligible_food_cannot_be_published(self):
        self.client.force_login(self.owner)
        for status, expiry in [
            ("STORED", timezone.localdate() - timedelta(days=1)),
            ("CONSUMED", timezone.localdate() + timedelta(days=1)),
            ("OFFERED", timezone.localdate() + timedelta(days=1)),
        ]:
            with self.subTest(status=status, expiry=expiry):
                self.food.status = status
                self.food.expiration_date = expiry
                self.food.save()
                response = self.client.post(reverse("sharedpost:create"), self.payload())
                self.assertIn("food_item", response.context["form"].errors)
                self.assertFalse(SharedPost.objects.exists())
                self.food.refresh_from_db()
                self.assertEqual(self.food.status, status)

    def test_food_expiring_today_can_be_published(self):
        self.food.expiration_date = timezone.localdate()
        self.food.save()
        self.client.force_login(self.owner)
        response = self.client.post(reverse("sharedpost:create"), self.payload())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(SharedPost.objects.count(), 1)

    def test_duplicate_publication_is_rejected(self):
        self.client.force_login(self.owner)
        self.client.post(reverse("sharedpost:create"), self.payload())
        response = self.client.post(reverse("sharedpost:create"), self.payload())
        self.assertIn("food_item", response.context["form"].errors)
        self.assertEqual(SharedPost.objects.count(), 1)

    def test_create_rolls_back_if_inventory_update_fails(self):
        self.client.force_login(self.owner)
        with patch.object(FoodItem, "save", side_effect=RuntimeError("inventory update failed")):
            with self.assertRaises(RuntimeError):
                self.client.post(reverse("sharedpost:create"), self.payload())
        self.assertFalse(SharedPost.objects.exists())
        self.food.refresh_from_db()
        self.assertEqual(self.food.status, "STORED")

    def test_owner_can_edit_location_and_description(self):
        post = self.make_post()
        new_location = Location.objects.create(owner=self.owner, area_name="Kukusan", latitude="-6.37", longitude="106.82")
        self.client.force_login(self.owner)
        response = self.client.post(reverse("sharedpost:update", args=[post.pk]), self.payload(location=new_location.pk, description="Ambil di pos satpam sebelum malam."))
        self.assertRedirects(response, reverse("sharedpost:list"), fetch_redirect_response=False)
        post.refresh_from_db()
        self.assertEqual(post.location_id, new_location.pk)
        self.assertEqual(post.description, "Ambil di pos satpam sebelum malam.")
        self.assertEqual(post.food_item_id, self.food.pk)
        self.food.refresh_from_db()
        self.assertEqual(self.food.status, "OFFERED")

    def test_edit_form_regular_and_htmx(self):
        post = self.make_post()
        self.client.force_login(self.owner)
        for is_htmx in [False, True]:
            with self.subTest(htmx=is_htmx):
                headers = {"HTTP_HX_REQUEST": "true"} if is_htmx else {}
                response = self.client.get(reverse("sharedpost:update", args=[post.pk]), **headers)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].fields["food_item"].disabled)
                self.assertEqual(response.context["form"].instance.pk, post.pk)
                self.assertTemplateUsed(response, "SharedPost/partials/update_form.html")
                if is_htmx:
                    self.assertNotContains(response, "<!doctype")
                else:
                    self.assertTemplateUsed(response, "SharedPost/update.html")

    def test_edit_htmx_returns_success_event(self):
        post = self.make_post()
        self.client.force_login(self.owner)
        response = self.client.post(reverse("sharedpost:update", args=[post.pk]), self.payload(description="Petunjuk baru untuk pengambilan."), HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["HX-Trigger"], "postUpdated")
        post.refresh_from_db()
        self.assertEqual(post.description, "Petunjuk baru untuk pengambilan.")

    def test_invalid_edit_keeps_original_data(self):
        post = self.make_post()
        self.client.force_login(self.owner)
        for is_htmx in [False, True]:
            with self.subTest(htmx=is_htmx):
                headers = {"HTTP_HX_REQUEST": "true"} if is_htmx else {}
                response = self.client.post(reverse("sharedpost:update", args=[post.pk]), self.payload(description="pendek"), **headers)
                self.assertIn("description", response.context["form"].errors)
                post.refresh_from_db()
                self.assertEqual(post.description, "Ambil di lobi kos pukul lima sore.")

    def test_edit_cannot_switch_food_or_take_foreign_location(self):
        post = self.make_post()
        other = self.make_other_user()
        other_food = FoodItem.objects.create(owner=other, name="Makanan lain", purchase_date=timezone.localdate(), expiration_date=timezone.localdate()+timedelta(days=2))
        other_location = Location.objects.create(owner=other, area_name="Lokasi lain", latitude="-6.36", longitude="106.83")
        self.client.force_login(self.owner)
        url = reverse("sharedpost:update", args=[post.pk])
        response = self.client.post(url, self.payload(food_item=other_food.pk))
        self.assertEqual(response.status_code, 302)
        post.refresh_from_db()
        self.assertEqual(post.food_item_id, self.food.pk)
        response = self.client.post(url, self.payload(location=other_location.pk))
        self.assertIn("location", response.context["form"].errors)
        post.refresh_from_db()
        self.assertEqual(post.location_id, self.location.pk)

    def test_owner_delete_returns_food_to_inventory(self):
        post = self.make_post()
        self.client.force_login(self.owner)
        response = self.client.post(reverse("sharedpost:delete", args=[post.pk]))
        self.assertRedirects(response, reverse("sharedpost:list"), fetch_redirect_response=False)
        self.assertFalse(SharedPost.objects.filter(pk=post.pk).exists())
        self.food.refresh_from_db()
        self.assertEqual(self.food.status, "STORED")
        self.assertTrue(SharedPostForm(user=self.owner).fields["food_item"].queryset.filter(pk=self.food.pk).exists())

    def test_delete_htmx_returns_updated_list_with_current_filters(self):
        post = self.make_post()
        self.client.force_login(self.owner)
        response = self.client.post(reverse("sharedpost:delete", args=[post.pk]), {"q": "Beji", "category": "GRAIN", "mine": "1"}, HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "SharedPost/partials/post_list.html")
        self.assertNotContains(response, "<!doctype")
        self.assertNotContains(response, "Roti gandum")
        self.assertFalse(SharedPost.objects.exists())
        self.food.refresh_from_db()
        self.assertEqual(self.food.status, "STORED")

    def test_owner_can_complete_post(self):
        post = self.make_post()
        self.client.force_login(self.owner)
        response = self.client.post(reverse("sharedpost:complete", args=[post.pk]))
        self.assertRedirects(response, reverse("sharedpost:list"), fetch_redirect_response=False)
        post.refresh_from_db()
        self.assertFalse(post.is_active)
        self.food.refresh_from_db()
        self.assertEqual(self.food.status, "CONSUMED")
        self.assertNotContains(self.client.get(reverse("sharedpost:list")), "Roti gandum")
        self.assertFalse(SharedPostForm(user=self.owner).fields["food_item"].queryset.filter(pk=self.food.pk).exists())

    def test_complete_htmx_returns_updated_list(self):
        post = self.make_post()
        self.client.force_login(self.owner)
        response = self.client.post(reverse("sharedpost:complete", args=[post.pk]), HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "SharedPost/partials/post_list.html")
        self.assertNotContains(response, "Roti gandum")
        post.refresh_from_db()
        self.assertFalse(post.is_active)
        self.food.refresh_from_db()
        self.assertEqual(self.food.status, "CONSUMED")

    def test_other_user_cannot_complete_post(self):
        post = self.make_post()
        self.client.force_login(self.make_other_user())
        response = self.client.post(reverse("sharedpost:complete", args=[post.pk]), HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 404)
        post.refresh_from_db()
        self.assertTrue(post.is_active)
        self.food.refresh_from_db()
        self.assertEqual(self.food.status, "OFFERED")

    def test_completed_post_cannot_be_edited_or_completed_again(self):
        post = self.make_post()
        self.client.force_login(self.owner)
        url = reverse("sharedpost:complete", args=[post.pk])
        self.client.post(url)
        self.assertEqual(self.client.post(url).status_code, 404)
        self.assertEqual(self.client.get(reverse("sharedpost:update", args=[post.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("sharedpost:update", args=[post.pk]), self.payload()).status_code, 404)

    def test_deleting_completed_history_does_not_restore_food(self):
        post = self.make_post()
        self.client.force_login(self.owner)
        self.client.post(reverse("sharedpost:complete", args=[post.pk]))
        self.client.post(reverse("sharedpost:delete", args=[post.pk]))
        self.assertFalse(SharedPost.objects.exists())
        self.food.refresh_from_db()
        self.assertEqual(self.food.status, "CONSUMED")

    def test_get_requests_do_not_delete_or_complete(self):
        post = self.make_post()
        self.client.force_login(self.owner)
        for action in ["delete", "complete"]:
            with self.subTest(action=action):
                self.assertEqual(self.client.get(reverse(f"sharedpost:{action}", args=[post.pk])).status_code, 405)
        post.refresh_from_db()
        self.assertTrue(post.is_active)
        self.food.refresh_from_db()
        self.assertEqual(self.food.status, "OFFERED")

    def test_csrf_is_required_for_all_mutations(self):
        post = self.make_post()
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        for action in ["create", "update", "delete", "complete"]:
            with self.subTest(action=action):
                args = [] if action == "create" else [post.pk]
                response = client.post(reverse(f"sharedpost:{action}", args=args), self.payload(), HTTP_HX_REQUEST="true")
                self.assertEqual(response.status_code, 403)
        post.refresh_from_db()
        self.assertTrue(post.is_active)
        self.food.refresh_from_db()
        self.assertEqual(self.food.status, "OFFERED")

    def test_missing_post_returns_404(self):
        self.client.force_login(self.owner)
        for action, method in [("detail", "get"), ("update", "get"), ("delete", "post"), ("complete", "post")]:
            with self.subTest(action=action):
                response = getattr(self.client, method)(reverse(f"sharedpost:{action}", args=[999999]))
                self.assertEqual(response.status_code, 404)

    def test_available_detail_and_owner_controls(self):
        post = self.make_post()
        url = reverse("sharedpost:detail", args=[post.pk])
        self.client.force_login(self.owner)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "SharedPost/detail.html")
        self.assertContains(response, "Edit penawaran")
        self.assertTrue(response.context["is_available"])
        self.client.force_login(self.make_other_user())
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ambil di lobi")
        self.assertNotContains(response, "Edit penawaran")
        self.assertFalse(response.context["is_owner"])
        listing = self.client.get(reverse("sharedpost:list"))
        self.assertContains(listing, url)
        self.assertNotContains(listing, "Hapus</button>")
        self.assertNotContains(listing, "Tandai Sudah Diambil")

    def test_unavailable_detail_is_visible_only_to_owner(self):
        post = self.make_post()
        other = self.make_other_user()
        url = reverse("sharedpost:detail", args=[post.pk])
        for active, status, expiry in [
            (False, "CONSUMED", timezone.localdate()+timedelta(days=1)),
            (True, "OFFERED", timezone.localdate()-timedelta(days=1)),
            (True, "STORED", timezone.localdate()+timedelta(days=1)),
        ]:
            with self.subTest(active=active, status=status):
                post.is_active = active; post.save()
                self.food.status = status; self.food.expiration_date = expiry; self.food.save()
                self.client.force_login(other)
                self.assertEqual(self.client.get(url).status_code, 404)
                self.client.force_login(self.owner)
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Tidak tersedia")
                self.assertNotContains(response, "Edit penawaran")

    def test_list_filters_and_excludes_unavailable_posts(self):
        post = self.make_post()
        other = self.make_other_user()
        other_location = Location.objects.create(owner=other, area_name="Kukusan", latitude="-6.37", longitude="106.82")
        other_food = FoodItem.objects.create(owner=other, name="Apel merah", category="FRUIT", status="OFFERED", purchase_date=timezone.localdate(), expiration_date=timezone.localdate())
        other_post = SharedPost.objects.create(food_item=other_food, location=other_location, description="Ambil sebelum malam hari.")
        self.client.force_login(self.owner)
        cases = [({}, {post.pk, other_post.pk}), ({"q": "ROTI"}, {post.pk}), ({"q": "kukusan"}, {other_post.pk}), ({"mine": "1"}, {post.pk}), ({"category": "FRUIT"}, {other_post.pk}), ({"q": "tidak ada"}, set()), ({"category": "GRAIN", "mine": "1", "q": "Beji"}, {post.pk})]
        for filters, expected in cases:
            with self.subTest(filters=filters):
                response = self.client.get(reverse("sharedpost:list"), filters, HTTP_HX_REQUEST="true")
                self.assertEqual(set(response.context["posts"].values_list("pk", flat=True)), expected)
        for active, status, expiry in [(False, "OFFERED", timezone.localdate()), (True, "CONSUMED", timezone.localdate()), (True, "OFFERED", timezone.localdate()-timedelta(days=1))]:
            with self.subTest(active=active, status=status, expiry=expiry):
                post.is_active=active; post.save()
                self.food.status=status; self.food.expiration_date=expiry; self.food.save()
                response=self.client.get(reverse("sharedpost:list"))
                self.assertNotIn(post, response.context["posts"])

    def test_description_html_is_escaped(self):
        post = self.make_post()
        post.description = '<script>alert("test")</script>'
        post.save()
        self.client.force_login(self.owner)
        for url in [reverse("sharedpost:list"), reverse("sharedpost:detail", args=[post.pk])]:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertNotContains(response, post.description)
                self.assertContains(response, "&lt;script&gt;")

    def test_model_enforces_single_active_post_per_food(self):
        self.make_post()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SharedPost.objects.create(food_item=self.food, location=self.location, description="Penawaran aktif kedua.")
        self.assertEqual(SharedPost.objects.count(), 1)
        history = SharedPost.objects.create(food_item=self.food, location=self.location, description="Riwayat yang sudah selesai.", is_active=False)
        self.assertFalse(history.is_active)

    def test_model_name_ordering_and_location_protection(self):
        post = self.make_post()
        self.assertEqual(str(post), "Roti gandum")
        self.assertIsNotNone(post.created_at)
        self.assertIsNotNone(post.updated_at)
        history = SharedPost.objects.create(food_item=self.food, location=self.location, description="Riwayat yang sudah selesai.", is_active=False)
        SharedPost.objects.filter(pk=post.pk).update(
            created_at=timezone.now() - timedelta(days=1)
        )
        self.assertEqual(list(SharedPost.objects.all()), [history, post])
        with self.assertRaises(RestrictedError):
            self.location.delete()
        self.food.delete()
        self.assertFalse(SharedPost.objects.exists())
