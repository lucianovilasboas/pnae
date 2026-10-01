from django.urls import path

from . import api

app_name = "students"

urlpatterns = [
    path("imports", api.import_create, name="import-create"),
    path("imports/<int:pk>/apply", api.import_apply, name="import-apply"),
    path("imports/<int:pk>/errors", api.import_errors, name="import-errors"),
    path("qr-export", api.qr_export, name="qr-export"),
]
