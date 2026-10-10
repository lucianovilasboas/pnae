"""Context processors do projeto."""

from config.version import APP_VERSION


def app_version(request):
    """Expõe a versão do app aos templates (rodapé e menu mobile)."""
    return {"app_version": APP_VERSION}


def active_campus(request):
    """Expõe o campus ativo e se o usuário pode trocá-lo (chip do cabeçalho)."""
    from apps.campus.selectors import resolve_campus

    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {"active_campus": None, "can_switch_campus": False}
    return {
        "active_campus": resolve_campus(user, request),
        "can_switch_campus": not getattr(user, "campus_id", None),
    }
