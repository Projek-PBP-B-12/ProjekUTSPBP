"""Pengaturan produksi diuji tanpa kredensial atau koneksi database server."""
import os
from pathlib import Path
import runpy
from unittest.mock import patch

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponse
from django.middleware.csrf import CsrfViewMiddleware, get_token
from django.test import RequestFactory, SimpleTestCase, override_settings


class DeploymentSettingsTests(SimpleTestCase):
    pws_host = "justin-evan-titiklapar.pws.cs.ui.ac.id"
    test_secret = "test-only-" + "deployment-settings-key-" * 3

    def load_settings(self, **environment):
        with patch.dict(os.environ, environment, clear=True), patch("dotenv.load_dotenv"):
            return runpy.run_path(str(Path(__file__).with_name("settings.py")))

    def test_local_defaults_allow_http_and_sqlite_without_a_production_secret(self):
        config = self.load_settings()
        self.assertTrue(config["DEBUG"])
        self.assertFalse(config["SESSION_COOKIE_SECURE"])
        self.assertFalse(config["CSRF_COOKIE_SECURE"])
        self.assertEqual(config["DATABASES"]["default"]["ENGINE"], "django.db.backends.sqlite3")
        self.assertEqual(config["SITE_URL"], "http://127.0.0.1:8000")

    def test_production_refuses_missing_or_blank_secret(self):
        for environment in [{}, {"SECRET_KEY": ""}, {"SECRET_KEY": "   "}]:
            with self.subTest(environment=environment):
                with self.assertRaisesMessage(ImproperlyConfigured, "Isi SECRET_KEY baru"):
                    self.load_settings(PRODUCTION="true", **environment)

    def test_production_defaults_disable_debug_and_require_https_cookies(self):
        config = self.load_settings(
            PRODUCTION=" True ", SECRET_KEY=self.test_secret,
            DB_NAME="test_database", DB_HOST="test.invalid", DB_PORT="5432",
            DB_USER="test_user", DB_PASSWORD="test-only-password", SCHEMA="test_schema",
        )
        self.assertFalse(config["DEBUG"])
        self.assertTrue(config["SESSION_COOKIE_SECURE"])
        self.assertTrue(config["CSRF_COOKIE_SECURE"])
        self.assertEqual(config["SECRET_KEY"], self.test_secret)
        self.assertEqual(config["DATABASES"]["default"]["ENGINE"], "django.db.backends.postgresql")
        self.assertEqual(config["DATABASES"]["default"]["NAME"], "test_database")
        self.assertEqual(config["DATABASES"]["default"]["OPTIONS"]["options"], "-c search_path=test_schema")
        self.assertEqual(config["SITE_URL"], f"https://{self.pws_host}")

    def test_environment_can_configure_hosts_origins_and_public_url(self):
        config = self.load_settings(
            PRODUCTION="true", SECRET_KEY=self.test_secret, DEBUG="false",
            ALLOWED_HOSTS=" app.example, api.example, ",
            CSRF_TRUSTED_ORIGINS=" https://app.example, https://api.example, ",
            SITE_URL="https://app.example/",
        )
        self.assertEqual(config["ALLOWED_HOSTS"], ["app.example", "api.example"])
        self.assertEqual(config["CSRF_TRUSTED_ORIGINS"], ["https://app.example", "https://api.example"])
        self.assertEqual(config["SITE_URL"], "https://app.example")

    def test_csrf_accepts_pws_origin_behind_proxy_and_rejects_foreign_origin(self):
        config = self.load_settings(PRODUCTION="true", SECRET_KEY=self.test_secret)
        with override_settings(
            ALLOWED_HOSTS=config["ALLOWED_HOSTS"],
            CSRF_TRUSTED_ORIGINS=config["CSRF_TRUSTED_ORIGINS"], DEBUG=False,
        ):
            for origin, allowed in [(f"https://{self.pws_host}", True), ("https://foreign.example", False)]:
                with self.subTest(origin=origin):
                    # HTTP di sisi Django, HTTPS di sisi browser setelah terminasi proxy.
                    request = RequestFactory().post(
                        "/accounts/login/", HTTP_HOST=self.pws_host, HTTP_ORIGIN=origin,
                    )
                    request.META["HTTP_X_CSRFTOKEN"] = get_token(request)
                    request.COOKIES[settings.CSRF_COOKIE_NAME] = request.META["CSRF_COOKIE"]
                    middleware = CsrfViewMiddleware(lambda request: HttpResponse("OK"))
                    middleware.process_request(request)
                    response = middleware.process_view(request, lambda request: HttpResponse("OK"), (), {})
                    if allowed:
                        self.assertIsNone(response)
                    else:
                        self.assertEqual(response.status_code, 403)
