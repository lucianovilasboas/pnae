"""Criação de cardápios em lote (um por dia do período)."""

from django.db import IntegrityError, transaction

from apps.audit.services import record_event
from apps.dates import MAX_BULK_ROWS, iter_dates

from .models import Menu


class MenuStateError(ValueError):
    pass


def plan_menus_bulk(*, campus, start_date, end_date, weekdays, meal_type):
    """Datas a criar e datas já existentes, sem gravar nada."""
    to_create, existing = [], []
    for day in iter_dates(start_date, end_date, weekdays):
        if Menu.objects.filter(campus=campus, service_date=day, meal_type=meal_type).exists():
            existing.append(day)
        else:
            to_create.append(day)
        if len(to_create) + len(existing) >= MAX_BULK_ROWS:
            break
    return to_create, existing


@transaction.atomic
def create_menus_bulk(
    *, campus, user, start_date, end_date, weekdays, meal_type, description, notes=""
):
    to_create, existing = plan_menus_bulk(
        campus=campus, start_date=start_date, end_date=end_date,
        weekdays=weekdays, meal_type=meal_type,
    )
    for day in to_create:
        Menu.objects.create(
            campus=campus,
            service_date=day,
            meal_type=meal_type,
            description=description,
            notes=notes,
            created_by=user,
        )
    record_event(
        action="menu.bulk_created",
        entity_type="Campus",
        entity_id=campus.pk,
        actor=user,
        campus=campus,
        metadata={
            "created": len(to_create),
            "skipped": len(existing),
            "start": str(start_date),
            "end": str(end_date),
            "mealType": meal_type,
        },
    )
    return {"created": len(to_create), "skipped": len(existing), "dates": to_create}


def update_menu(*, menu, user, service_date, meal_type, description, notes=""):
    """Edita um cardápio existente (respeita o único campus/data/refeição)."""
    menu.service_date = service_date
    menu.meal_type = meal_type
    menu.description = description
    menu.notes = notes
    try:
        with transaction.atomic():
            menu.save(update_fields=["service_date", "meal_type", "description", "notes"])
    except IntegrityError as exc:
        raise MenuStateError("Já existe um cardápio para este campus, data e refeição.") from exc
    record_event(
        action="menu.updated",
        entity_type="Menu",
        entity_id=menu.pk,
        actor=user,
        campus=menu.campus,
        metadata={"serviceDate": str(service_date), "mealType": meal_type},
    )
    return menu


def delete_menu(*, menu, user):
    """Exclui um cardápio; bloqueia se houver distribuição vinculada (histórico)."""
    from apps.distributions.models import Distribution

    linked = Distribution.objects.filter(menu=menu).count()
    if linked:
        raise MenuStateError(
            f"Cardápio vinculado a {linked} distribuição(ões); "
            "remova ou cancele essas distribuições antes."
        )
    pk = menu.pk
    campus = menu.campus
    menu.delete()
    record_event(
        action="menu.deleted",
        entity_type="Menu",
        entity_id=pk,
        actor=user,
        campus=campus,
        metadata={},
    )
