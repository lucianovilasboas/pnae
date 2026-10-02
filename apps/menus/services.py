"""Criação de cardápios em lote (um por dia do período)."""

from django.db import transaction

from apps.audit.services import record_event
from apps.dates import MAX_BULK_ROWS, iter_dates

from .models import Menu


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
