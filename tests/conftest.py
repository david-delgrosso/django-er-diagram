# conftest.py

import pytest
from django.conf import settings
from django.apps import apps, AppConfig
import django
from pathlib import Path


# Fixture to set up Django settings for the test environment
@pytest.fixture(scope="session", autouse=True)
def django_db_setup():
    if not settings.configured:
        base_dir = Path(__file__).resolve().parent.parent
        settings.configure(
            INSTALLED_APPS=[
                "django.contrib.contenttypes",
                "django_er_diagram",
                "tests.mock_app",
            ],
            DATABASES={
                "default": {
                    "ENGINE": "django.db.backends.sqlite3",
                    "NAME": ":memory:",
                }
            },
            TEMPLATES=[
                {
                    "BACKEND": "django.template.backends.django.DjangoTemplates",
                    "DIRS": ["django_er_diagram.templates"],
                    "APP_DIRS": True,
                    "OPTIONS": {"context_processors": []},
                }
            ],
            BASE_DIR=base_dir,
        )
    django.setup()


# Fixture to register a mock app for testing
@pytest.fixture(scope="session", autouse=True)
def register_mock_app():
    # Dynamically create and register a mock app config
    class MockAppConfig(AppConfig):
        name = "tests.mock_app"
        label = "mock_app"
        path = "tests/mock_app"

        def ready(self):
            from tests.mock_app.models import Author, Book, Review

            # Register mock models
            apps.register_model(self.label, Author)
            apps.register_model(self.label, Book)
            apps.register_model(self.label, Review)

    # Set up a temporary app in Django's registry
    if not apps.is_installed("tests.mock_app"):
        apps.app_configs["mock_app"] = MockAppConfig("mock_app", "mock_app")
        apps.set_installed_apps(["tests.mock_app"] + list(settings.INSTALLED_APPS))
        apps.clear_cache()

    yield  # Provide a teardown point if needed

    # Remove the mock app after the tests
    if "mock_app" in apps.app_configs:
        del apps.app_configs["mock_app"]
        apps.set_installed_apps(
            [app for app in settings.INSTALLED_APPS if app != "mock_app"]
        )
        apps.clear_cache()
