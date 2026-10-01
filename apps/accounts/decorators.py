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


def is_operator(user) -> bool:
    """Administrador ou operador PNAE (pode operar distribuição)."""
    return bool(
        user
        and user.is_authenticated
        and (user.is_superuser or user.role in {UserRole.ADMIN, UserRole.OPERATOR})
    )


def can_authorize(user) -> bool:
    return bool(
        user
        and user.is_authenticated
        and (user.is_superuser or user.role == UserRole.ADMIN or user.can_authorize_extras)
    )


def can_reverse(user) -> bool:
    return bool(
        user
        and user.is_authenticated
        and (user.is_superuser or user.role == UserRole.ADMIN or user.can_reverse_deliveries)
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


def _api_authenticated(request):
    if not request.user.is_authenticated:
        return JsonResponse(
            {"detail": "Autenticação necessária.", "code": "not_authenticated"},
            status=401,
        )
    return None


def _api_requires(request, predicate):
    denied = _api_authenticated(request)
    if denied:
        return denied
    if not predicate(request.user):
        return JsonResponse({"detail": "Permissão negada.", "code": "forbidden"}, status=403)
    return None


def api_operator_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        denied = _api_requires(request, is_operator)
        if denied:
            return denied
        return view(request, *args, **kwargs)

    return wrapper


def api_authorize_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        denied = _api_requires(request, can_authorize)
        if denied:
            return denied
        return view(request, *args, **kwargs)

    return wrapper


def api_reverse_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        denied = _api_requires(request, can_reverse)
        if denied:
            return denied
        return view(request, *args, **kwargs)

    return wrapper
