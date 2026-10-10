"""Páginas de contexto do campus (escolha do campus ativo)."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from .models import Campus
from .selectors import resolve_campus

SESSION_KEY = "campus_id"


def can_switch_campus(user) -> bool:
    """Só quem **não** tem campus vinculado pode trocar de campus."""
    return not getattr(user, "campus_id", None)


def _safe_next(request):
    target = request.POST.get("next") or request.GET.get("next")
    if target and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return target
    return None


@login_required
def campus_select(request):
    if request.method == "POST":
        if not can_switch_campus(request.user):
            messages.error(request, "Seu usuário está vinculado a um campus.")
            return redirect("campus:select")
        campus = Campus.objects.filter(
            pk=request.POST.get("campus"), active=True
        ).first()
        if campus is None:
            messages.error(request, "Selecione um campus válido.")
        else:
            request.session[SESSION_KEY] = campus.pk
            messages.success(request, f"Campus ativo: {campus.name}.")
            return redirect(_safe_next(request) or "distributions:home")
        return redirect("campus:select")

    return render(
        request,
        "campus/select.html",
        {
            "campuses": Campus.objects.filter(active=True).order_by("name"),
            "current": resolve_campus(request.user, request),
            "can_switch": can_switch_campus(request.user),
            "next": request.GET.get("next", ""),
            "breadcrumbs": [{"label": "Início", "url": "/"}, {"label": "Campus"}],
        },
    )
