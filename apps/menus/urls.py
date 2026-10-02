from django.urls import path

from . import views

app_name = "menus"

urlpatterns = [
    path("", views.menu_list, name="list"),
]
