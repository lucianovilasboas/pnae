from django.urls import path

from . import api

app_name = "menus_api"

urlpatterns = [
    path("", api.menu_create, name="create"),
]
