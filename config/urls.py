"""Roteamento de URLs do IFMG Alimenta."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from apps.audit.views import healthcheck
from config.pwa import manifest, service_worker

urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz/", healthcheck, name="healthcheck"),
    path("manifest.webmanifest", manifest, name="manifest"),
    path("service-worker.js", service_worker, name="service-worker"),
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("api/students/", include("apps.students.urls")),
    path("api/", include("apps.distributions.urls")),
    path("estudantes/", include("apps.students.urls_pages")),
    path("cardapios/", include("apps.menus.urls")),
    path("auditoria/", include("apps.audit.urls")),
    path("", include("apps.distributions.urls_pages")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
