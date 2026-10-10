"""Página de cadastro de cardápios (admin/operador)."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.http import url_has_allowed_host_and_scheme

from apps.accounts.decorators import is_operator
from apps.audit.services import record_event
from apps.campus.selectors import resolve_campus

from .models import MealType, Menu
from .services import MenuStateError, create_menu, delete_menu, update_menu


def _safe_redirect(request, fallback):
    """Redireciona para ``voltar`` (GET/POST) só se for destino interno seguro."""
    target = request.POST.get("voltar") or request.GET.get("voltar")
    if target and url_has_allowed_host_and_scheme(
        target,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(target)
    return redirect(fallback)


@login_required
def menu_list(request):
    if not is_operator(request.user):
        return HttpResponseForbidden("Apenas operadores e administradores.")

    campus = resolve_campus(request.user, request)

    if request.method == "POST":
        action = request.POST.get("action", "create")

        if action == "delete":
            menu = get_object_or_404(Menu, pk=request.POST.get("id"))
            if campus is not None and menu.campus_id != campus.pk and not request.user.is_superuser:
                messages.error(request, "Cardápio de outro campus.")
            else:
                try:
                    delete_menu(menu=menu, user=request.user)
                    messages.success(request, "Cardápio excluído.")
                except MenuStateError as exc:
                    messages.error(request, str(exc))
            return redirect("menus:list")

        if action in {"publish", "unpublish"}:
            menu = get_object_or_404(Menu, pk=request.POST.get("id"))
            if campus is not None and menu.campus_id != campus.pk and not request.user.is_superuser:
                messages.error(request, "Cardápio de outro campus.")
            else:
                publish = action == "publish"
                menu.published = publish
                menu.published_at = timezone.now() if publish else None
                menu.published_by = request.user if publish else None
                menu.save(update_fields=["published", "published_at", "published_by"])
                record_event(
                    action="menu.published" if publish else "menu.unpublished",
                    entity_type="Menu",
                    entity_id=menu.pk,
                    actor=request.user,
                    campus=menu.campus,
                    metadata={"serviceDate": str(menu.service_date)},
                )
                messages.success(
                    request,
                    "Cardápio publicado para os alunos."
                    if publish
                    else "Cardápio despublicado.",
                )
            return redirect("menus:list")

        if campus is None:
            messages.error(request, "Selecione o campus para cadastrar o cardápio.")
            return _safe_redirect(request, "menus:list")

        service_date = parse_date(request.POST.get("service_date", "") or "")
        meal_type = request.POST.get("meal_type") or MealType.SNACK
        description = (request.POST.get("description") or "").strip()
        if not (service_date and description):
            messages.error(request, "Informe a data e a descrição do cardápio.")
        else:
            try:
                create_menu(
                    campus=campus,
                    user=request.user,
                    service_date=service_date,
                    meal_type=meal_type,
                    description=description,
                    notes=(request.POST.get("notes") or "").strip(),
                )
                messages.success(request, "Cardápio cadastrado.")
            except MenuStateError as exc:
                messages.error(request, str(exc))
        return _safe_redirect(request, "menus:list")

    queryset = Menu.objects.none()
    if campus is not None:
        queryset = Menu.objects.filter(campus=campus)

    de = parse_date(request.GET.get("de", "") or "")
    ate = parse_date(request.GET.get("ate", "") or "")
    if de:
        queryset = queryset.filter(service_date__gte=de)
    if ate:
        queryset = queryset.filter(service_date__lte=ate)
    queryset = queryset.order_by("-service_date", "meal_type")

    # Só aceita `voltar` interno (evita open redirect / href inseguro).
    voltar = request.GET.get("voltar", "")
    if not (
        voltar
        and url_has_allowed_host_and_scheme(
            voltar, allowed_hosts={request.get_host()}, require_https=request.is_secure()
        )
    ):
        voltar = ""

    paginator = Paginator(queryset, 20)
    page = paginator.get_page(request.GET.get("page"))
    query = request.GET.copy()
    query.pop("page", None)

    return render(
        request,
        "menus/list.html",
        {
            "menus": page.object_list,
            "page": page,
            "querystring": query.urlencode(),
            "campus": campus,
            "meal_types": MealType.choices,
            "filters": {"de": request.GET.get("de", ""), "ate": request.GET.get("ate", "")},
            # Pré-preenchimento ao chegar da tela de Distribuições ("+").
            "prefill": {
                "service_date": request.GET.get("data", ""),
                "meal_type": request.GET.get("refeicao", "").strip() or MealType.SNACK,
                "voltar": voltar,
            },
            "breadcrumbs": [
                {"label": "Início", "url": "/"},
                {"label": "Cardápios"},
            ],
        },
    )


@login_required
def menu_edit(request, pk):
    if not is_operator(request.user):
        return HttpResponseForbidden("Apenas operadores e administradores.")

    campus = resolve_campus(request.user, request)
    menu = get_object_or_404(Menu, pk=pk)
    if campus is not None and menu.campus_id != campus.pk and not request.user.is_superuser:
        messages.error(request, "Cardápio de outro campus.")
        return redirect("menus:list")

    if request.method == "POST":
        service_date = parse_date(request.POST.get("service_date", "") or "")
        meal_type = request.POST.get("meal_type") or MealType.SNACK
        description = (request.POST.get("description") or "").strip()
        notes = (request.POST.get("notes") or "").strip()
        if not (service_date and description):
            messages.error(request, "Informe a data e a descrição do cardápio.")
        else:
            try:
                update_menu(
                    menu=menu, user=request.user, service_date=service_date,
                    meal_type=meal_type, description=description, notes=notes,
                )
                messages.success(request, "Cardápio atualizado.")
                return redirect("menus:list")
            except MenuStateError as exc:
                messages.error(request, str(exc))

    return render(
        request,
        "menus/edit.html",
        {
            "menu": menu,
            "meal_types": MealType.choices,
            "breadcrumbs": [
                {"label": "Início", "url": "/"},
                {"label": "Cardápios", "url": "/cardapios/"},
                {"label": "Editar"},
            ],
        },
    )
