from django.urls import path

from . import views

app_name = "menus"

urlpatterns = [
    path("", views.menu_list, name="list"),
    path("<int:pk>/editar/", views.menu_edit, name="edit"),
]
