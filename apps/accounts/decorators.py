"""Decoradores de autorização para endpoints JSON."""

from functools import wraps

from django.http import JsonResponse

from .models import UserRole


def is_admin(user) -> bool:
    return bool(
        user
        and user.is_authenticated
        and (user.is_superuser or user.role == UserRole.ADMIN)
    )


def api_login_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(
                {"detail": "Autenticação necessária.", "code": "not_authenticated"},
                status=401,
            )
        return view(request, *args, **kwargs)

    return wrapper


def api_admin_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(
                {"detail": "Autenticação necessária.", "code": "not_authenticated"},
                status=401,
            )
        if not is_admin(request.user):
            return JsonResponse(
                {"detail": "Permissão negada.", "code": "forbidden"}, status=403
            )
        return view(request, *args, **kwargs)

    return wrapper
