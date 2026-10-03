"""Página de cadastro de cardápios (admin/operador)."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date

from apps.accounts.decorators import is_operator
from apps.audit.services import record_event
from apps.campus.selectors import resolve_campus

from .models import MealType, Menu
from .services import MenuStateError, delete_menu, update_menu


@login_required
def menu_list(request):
    if not is_operator(request.user):
        return HttpResponseForbidden("Apenas operadores e administradores.")

    campus = resolve_campus(request.user, request)

    if request.method == "POST":
        if campus is None:
            messages.error(request, "Campus não definido.")
            return redirect("menus:list")

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

        service_date = parse_date(request.POST.get("service_date", "") or "")
        meal_type = request.POST.get("meal_type") or MealType.SNACK
        description = (request.POST.get("description") or "").strip()
        if not (service_date and description):
            messages.error(request, "Informe a data e a descrição do cardápio.")
        else:
            menu = Menu.objects.create(
                campus=campus,
                service_date=service_date,
                meal_type=meal_type,
                description=description,
                notes=(request.POST.get("notes") or "").strip(),
                created_by=request.user,
            )
            record_event(
                action="menu.created",
                entity_type="Menu",
                entity_id=menu.pk,
                actor=request.user,
                campus=campus,
                metadata={"serviceDate": str(service_date), "mealType": meal_type},
            )
            messages.success(request, "Cardápio cadastrado.")
        return redirect("menus:list")

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
