"""Página de cadastro de cardápios (admin/operador)."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.utils.dateparse import parse_date

from apps.accounts.decorators import is_operator
from apps.audit.services import record_event
from apps.campus.selectors import resolve_campus

from .models import MealType, Menu


@login_required
def menu_list(request):
    if not is_operator(request.user):
        return HttpResponseForbidden("Apenas operadores e administradores.")

    campus = resolve_campus(request.user, request)

    if request.method == "POST":
        if campus is None:
            messages.error(request, "Campus não definido.")
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
        },
    )
