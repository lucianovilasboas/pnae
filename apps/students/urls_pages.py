from django.urls import path

from . import views

app_name = "students_pages"

urlpatterns = [
    path("importar/", views.import_page, name="import-page"),
    path("importar/<int:pk>/confirmar/", views.import_confirm, name="import-confirm"),
    path("qr/", views.qr_page, name="qr-page"),
]
