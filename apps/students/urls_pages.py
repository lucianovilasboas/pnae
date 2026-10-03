from django.urls import path

from . import views

app_name = "students_pages"

urlpatterns = [
    path("", views.student_list, name="student-list"),
    path("novo/", views.student_create, name="student-create"),
    path("<int:pk>/editar/", views.student_edit, name="student-edit"),
    path("<int:pk>/inativar/", views.student_deactivate, name="student-deactivate"),
    path("importar/", views.import_page, name="import-page"),
    path("importar/<int:pk>/confirmar/", views.import_confirm, name="import-confirm"),
    path("qr/", views.qr_page, name="qr-page"),
]
