from django.conf import settings

DJANGO_ER_DIAGRAM_ONLY_APPS = getattr(settings, "DJANGO_ER_DIAGRAM_ONLY_APPS", [])
DJANGO_ER_DIAGRAM_IGNORE_APPS = getattr(settings, "DJANGO_ER_DIAGRAM_IGNORE_APPS", [])
