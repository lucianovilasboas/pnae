"""Endpoints JSON de cardápios.

O atalho "+" da tela de distribuições cria um cardápio único por aqui, sem sair
da página, para não perder os valores já preenchidos no formulário.
"""

import json

from django.http import JsonResponse
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from apps.accounts.decorators import api_operator_required
from apps.campus.models import Campus
from apps.campus.selectors import resolve_campus

from .models import MealType
from .services import MenuStateError, create_menu


def _payload(request) -> dict:
    if request.content_type == "application/json" and request.body:
        try:
            return json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            return {}
    return request.POST.dict()


@require_POST
@api_operator_required
def menu_create(request):
    data = _payload(request)
    # Campus do usuário / único ativo; senão, o informado no corpo (admin global).
    campus = resolve_campus(request.user, None)
    if campus is None and data.get("campus"):
        campus = Campus.objects.filter(pk=data["campus"], active=True).first()
    if campus is None:
        return JsonResponse({"detail": "Selecione o campus.", "code": "no_campus"}, status=400)

    service_date = parse_date(data.get("service_date", "") or "")
    meal_type = data.get("meal_type") or MealType.SNACK
    description = (data.get("description") or "").strip()
    if not (service_date and description):
        return JsonResponse(
            {"detail": "Informe a data e a descrição do cardápio.", "code": "invalid_payload"},
            status=400,
        )
    if meal_type not in MealType.values:
        return JsonResponse({"detail": "Refeição inválida.", "code": "invalid_payload"}, status=400)

    try:
        menu = create_menu(
            campus=campus,
            user=request.user,
            service_date=service_date,
            meal_type=meal_type,
            description=description,
            notes=(data.get("notes") or "").strip(),
        )
    except MenuStateError as exc:
        return JsonResponse({"detail": str(exc), "code": "duplicate"}, status=409)

    return JsonResponse(
        {
            "id": menu.pk,
            "serviceDate": str(menu.service_date),
            "mealType": menu.meal_type,
            "label": f"{menu.service_date} — {menu.get_meal_type_display()}: {menu.description}",
        },
        status=201,
    )
