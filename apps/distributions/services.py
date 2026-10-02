"""Regras de negócio de distribuição e entrega.

Toda operação relevante é transacional e gera `AuditEvent`. A duplicidade de
entrega regular é decidida pela constraint do banco (índice único parcial);
aqui apenas interpretamos o `IntegrityError`. Ver docs/05-testes.md.
"""

from dataclasses import dataclass
from datetime import datetime

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.audit.services import record_event
from apps.dates import MAX_BULK_ROWS, iter_dates
from apps.menus.models import Menu
from apps.students.models import Student
from apps.students.tokens import hash_token

from .models import (
    Delivery,
    DeliveryStatus,
    DeliveryType,
    Distribution,
    DistributionStatus,
)


class DistributionStateError(ValueError):
    pass


@dataclass
class ScanResult:
    result: str
    student: Student | None = None
    delivery: Delivery | None = None
    previous_delivery: Delivery | None = None
    message: str = ""


# ---------------------------------------------------------------------------
# Ciclo de vida da distribuição
# ---------------------------------------------------------------------------
def create_distribution(
    *,
    campus,
    user,
    service_date,
    meal_type,
    planned_start_at,
    planned_end_at,
    menu=None,
    estimated_quantity=None,
):
    distribution = Distribution.objects.create(
        campus=campus,
        menu=menu,
        service_date=service_date,
        meal_type=meal_type,
        planned_start_at=planned_start_at,
        planned_end_at=planned_end_at,
        estimated_quantity=estimated_quantity,
        status=DistributionStatus.DRAFT,
    )
    record_event(
        action="distribution.created",
        entity_type="Distribution",
        entity_id=distribution.pk,
        actor=user,
        campus=campus,
        metadata={"serviceDate": str(service_date), "mealType": meal_type},
    )
    return distribution


def open_distribution(*, distribution, user):
    if distribution.status != DistributionStatus.DRAFT:
        raise DistributionStateError("Só é possível abrir uma distribuição em rascunho.")
    distribution.status = DistributionStatus.OPEN
    distribution.opened_by = user
    distribution.opened_at = timezone.now()
    distribution.save(update_fields=["status", "opened_by", "opened_at", "updated_at"])
    record_event(
        action="distribution.opened",
        entity_type="Distribution",
        entity_id=distribution.pk,
        actor=user,
        campus=distribution.campus,
    )
    return distribution


def close_distribution(*, distribution, user):
    if distribution.status != DistributionStatus.OPEN:
        raise DistributionStateError("Só é possível encerrar uma distribuição aberta.")
    distribution.status = DistributionStatus.CLOSED
    distribution.closed_by = user
    distribution.closed_at = timezone.now()
    distribution.save(update_fields=["status", "closed_by", "closed_at", "updated_at"])
    record_event(
        action="distribution.closed",
        entity_type="Distribution",
        entity_id=distribution.pk,
        actor=user,
        campus=distribution.campus,
    )
    return distribution


def reopen_distribution(*, distribution, user):
    """Reabre uma distribuição encerrada **do dia de hoje** (RN: só no mesmo dia)."""
    if distribution.status != DistributionStatus.CLOSED:
        raise DistributionStateError("Só é possível reabrir uma distribuição encerrada.")
    if distribution.service_date != timezone.localdate():
        raise DistributionStateError(
            "Só é possível reabrir uma distribuição encerrada do dia de hoje."
        )
    try:
        with transaction.atomic():
            distribution.status = DistributionStatus.OPEN
            distribution.opened_by = user
            distribution.opened_at = timezone.now()
            distribution.closed_by = None
            distribution.closed_at = None
            distribution.save(
                update_fields=[
                    "status", "opened_by", "opened_at",
                    "closed_by", "closed_at", "updated_at",
                ]
            )
    except IntegrityError as exc:
        distribution.refresh_from_db()
        raise DistributionStateError(
            "Já existe uma distribuição aberta para este campus, data e refeição."
        ) from exc

    record_event(
        action="distribution.reopened",
        entity_type="Distribution",
        entity_id=distribution.pk,
        actor=user,
        campus=distribution.campus,
    )
    return distribution


# ---------------------------------------------------------------------------
# Leitura e entrega
# ---------------------------------------------------------------------------
def record_scan(*, distribution, token, user):
    """Tenta registrar entrega REGULAR de forma atômica."""
    if distribution.status != DistributionStatus.OPEN:
        return ScanResult("DISTRIBUTION_CLOSED", message="Distribuição não está aberta.")
    if not token:
        return ScanResult("INVALID_TOKEN", message="QR inválido.")

    student = (
        Student.objects.filter(
            campus_id=distribution.campus_id, qr_token_hash=hash_token(token)
        )
        .select_related("class_group")
        .first()
    )
    if student is None:
        return ScanResult("INVALID_TOKEN", message="QR não reconhecido.")
    if not student.active:
        return ScanResult("INELIGIBLE", student=student, message="Estudante inativo.")

    try:
        # A constraint única parcial decide quem vence em caso de concorrência.
        with transaction.atomic():
            delivery = Delivery.objects.create(
                distribution=distribution,
                student=student,
                delivery_type=DeliveryType.REGULAR,
                recorded_by=user,
            )
    except IntegrityError:
        previous = Delivery.objects.filter(
            distribution=distribution,
            student=student,
            delivery_type=DeliveryType.REGULAR,
            status=DeliveryStatus.VALIDA,
        ).first()
        return ScanResult(
            "ALREADY_DELIVERED",
            student=student,
            previous_delivery=previous,
            message="Entrega regular já registrada nesta distribuição.",
        )

    record_event(
        action="delivery.recorded",
        entity_type="Delivery",
        entity_id=delivery.pk,
        actor=user,
        campus=distribution.campus,
        metadata={
            "distribution": distribution.pk,
            "student": student.pk,
            "type": DeliveryType.REGULAR,
        },
    )
    return ScanResult(
        "DELIVERED", student=student, delivery=delivery, message="Entrega registrada."
    )


def register_extra(*, distribution, student, reason, recorded_by, authorized_by):
    if distribution.status != DistributionStatus.OPEN:
        raise DistributionStateError("Distribuição não está aberta.")
    if not reason or not reason.strip():
        raise DistributionStateError("Motivo obrigatório para entrega excedente.")

    delivery = Delivery.objects.create(
        distribution=distribution,
        student=student,
        delivery_type=DeliveryType.EXCEDENTE,
        reason=reason.strip(),
        recorded_by=recorded_by,
        authorized_by=authorized_by,
    )
    record_event(
        action="delivery.extra",
        entity_type="Delivery",
        entity_id=delivery.pk,
        actor=recorded_by,
        campus=distribution.campus,
        metadata={
            "distribution": distribution.pk,
            "student": student.pk,
            "authorizedBy": authorized_by.pk,
        },
    )
    return delivery


def reverse_delivery(*, delivery, reason, user):
    if delivery.status != DeliveryStatus.VALIDA:
        raise DistributionStateError("Esta entrega já foi estornada.")
    if not reason or not reason.strip():
        raise DistributionStateError("Motivo obrigatório para estorno.")

    delivery.status = DeliveryStatus.ESTORNADA
    delivery.reversed_at = timezone.now()
    delivery.reversed_by = user
    delivery.reversal_reason = reason.strip()
    delivery.save(
        update_fields=["status", "reversed_at", "reversed_by", "reversal_reason"]
    )
    record_event(
        action="delivery.reversed",
        entity_type="Delivery",
        entity_id=delivery.pk,
        actor=user,
        campus=delivery.distribution.campus,
        metadata={"distribution": delivery.distribution_id, "student": delivery.student_id},
    )
    return delivery


# ---------------------------------------------------------------------------
# Indicadores
# ---------------------------------------------------------------------------
def distribution_summary(distribution) -> dict:
    eligible = Student.objects.filter(
        campus_id=distribution.campus_id, active=True
    ).count()
    valid = Delivery.objects.filter(
        distribution=distribution, status=DeliveryStatus.VALIDA
    )
    regular = valid.filter(delivery_type=DeliveryType.REGULAR).count()
    extras = valid.filter(delivery_type=DeliveryType.EXCEDENTE).count()
    reversed_count = Delivery.objects.filter(
        distribution=distribution, status=DeliveryStatus.ESTORNADA
    ).count()
    return {
        "eligible": eligible,
        "regularValid": regular,
        "extrasValid": extras,
        "pending": max(eligible - regular, 0),
        "reversed": reversed_count,
        "attendanceRate": round(regular / eligible, 3) if eligible else 0.0,
    }


def pending_students(distribution, class_group=None):
    delivered_ids = Delivery.objects.filter(
        distribution=distribution,
        delivery_type=DeliveryType.REGULAR,
        status=DeliveryStatus.VALIDA,
    ).values_list("student_id", flat=True)
    queryset = (
        Student.objects.filter(campus_id=distribution.campus_id, active=True)
        .exclude(id__in=delivered_ids)
        .select_related("class_group")
        .order_by("full_name")
    )
    if class_group is not None:
        queryset = queryset.filter(class_group=class_group)
    return queryset


def distribution_report(distribution) -> dict:
    """Dados do relatório diário, com reconciliação por tipo/status."""
    deliveries = Delivery.objects.filter(distribution=distribution).select_related(
        "student", "student__class_group", "recorded_by", "authorized_by", "reversed_by"
    )
    regular = deliveries.filter(
        delivery_type=DeliveryType.REGULAR, status=DeliveryStatus.VALIDA
    )
    extras = deliveries.filter(
        delivery_type=DeliveryType.EXCEDENTE, status=DeliveryStatus.VALIDA
    )
    reversed_deliveries = deliveries.filter(status=DeliveryStatus.ESTORNADA)

    by_class = []
    for group in distribution.campus.class_groups.filter(active=True).order_by("name"):
        eligible = Student.objects.filter(
            campus_id=distribution.campus_id, active=True, class_group=group
        ).count()
        served = regular.filter(student__class_group=group).count()
        by_class.append(
            {
                "name": group.name,
                "eligible": eligible,
                "regular": served,
                "pending": max(eligible - served, 0),
            }
        )
    without_class = Student.objects.filter(
        campus_id=distribution.campus_id, active=True, class_group__isnull=True
    ).count()
    if without_class:
        served = regular.filter(student__class_group__isnull=True).count()
        by_class.append(
            {
                "name": "Sem turma",
                "eligible": without_class,
                "regular": served,
                "pending": max(without_class - served, 0),
            }
        )

    return {
        "summary": distribution_summary(distribution),
        "regular": regular.order_by("student__full_name"),
        "extras": extras.order_by("student__full_name"),
        "reversed_deliveries": reversed_deliveries.order_by("student__full_name"),
        "by_class": by_class,
    }


def report_rows(distribution):
    """Linhas planas para o CSV (inclui excedentes e estornadas)."""
    rows = []
    for delivery in (
        Delivery.objects.filter(distribution=distribution)
        .select_related(
            "student", "student__class_group", "recorded_by", "authorized_by", "reversed_by"
        )
        .order_by("delivered_at")
    ):
        rows.append(
            {
                "matricula": delivery.student.registration_number,
                "nome": delivery.student.full_name,
                "turma": delivery.student.class_group.label if delivery.student.class_group else "",
                "tipo": delivery.delivery_type,
                "situacao": delivery.status,
                "entregue_em": delivery.delivered_at.isoformat(),
                "registrado_por": getattr(delivery.recorded_by, "email", ""),
                "autorizado_por": getattr(delivery.authorized_by, "email", ""),
                "motivo": delivery.reason or "",
                "estornado_por": getattr(delivery.reversed_by, "email", ""),
                "motivo_estorno": delivery.reversal_reason or "",
            }
        )
    return rows


# ---------------------------------------------------------------------------
# Criação em lote (período × dias da semana)
# ---------------------------------------------------------------------------
def plan_distributions_bulk(*, campus, start_date, end_date, weekdays, meal_type):
    """Datas a criar e datas já existentes, sem gravar nada."""
    to_create, existing = [], []
    for day in iter_dates(start_date, end_date, weekdays):
        if Distribution.objects.filter(
            campus=campus, service_date=day, meal_type=meal_type
        ).exists():
            existing.append(day)
        else:
            to_create.append(day)
        if len(to_create) + len(existing) >= MAX_BULK_ROWS:
            break
    return to_create, existing


@transaction.atomic
def create_distributions_bulk(
    *,
    campus,
    user,
    start_date,
    end_date,
    weekdays,
    meal_type,
    start_time,
    end_time,
    estimated_quantity=None,
    auto_open=True,
):
    """Cria rascunhos para os dias do período; vincula o cardápio do dia se houver."""
    to_create, existing = plan_distributions_bulk(
        campus=campus,
        start_date=start_date,
        end_date=end_date,
        weekdays=weekdays,
        meal_type=meal_type,
    )
    tz = timezone.get_current_timezone()
    for day in to_create:
        day_menu = Menu.objects.filter(
            campus=campus, service_date=day, meal_type=meal_type
        ).first()
        Distribution.objects.create(
            campus=campus,
            menu=day_menu,
            service_date=day,
            meal_type=meal_type,
            planned_start_at=timezone.make_aware(datetime.combine(day, start_time), tz),
            planned_end_at=timezone.make_aware(datetime.combine(day, end_time), tz),
            estimated_quantity=estimated_quantity,
            status=DistributionStatus.DRAFT,
            auto_open=auto_open,
        )

    record_event(
        action="distribution.bulk_created",
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


# ---------------------------------------------------------------------------
# Edição, exclusão e cancelamento
# ---------------------------------------------------------------------------
def update_distribution(*, distribution, user, **fields):
    """Edita uma distribuição em rascunho. Campos permitidos vêm da view."""
    if distribution.status != DistributionStatus.DRAFT:
        raise DistributionStateError("Só é possível editar uma distribuição em rascunho.")
    for key, value in fields.items():
        setattr(distribution, key, value)
    distribution.save()
    record_event(
        action="distribution.updated",
        entity_type="Distribution",
        entity_id=distribution.pk,
        actor=user,
        campus=distribution.campus,
        metadata={"fields": sorted(fields.keys())},
    )
    return distribution


def delete_distribution(*, distribution, user):
    """Exclui uma distribuição em rascunho (sem entregas)."""
    if distribution.status != DistributionStatus.DRAFT:
        raise DistributionStateError("Só é possível excluir uma distribuição em rascunho.")
    if distribution.deliveries.exists():
        raise DistributionStateError(
            "Esta distribuição já tem entregas e não pode ser excluída."
        )
    pk = distribution.pk
    campus = distribution.campus
    distribution.delete()
    record_event(
        action="distribution.deleted",
        entity_type="Distribution",
        entity_id=pk,
        actor=user,
        campus=campus,
        metadata={},
    )


def cancel_distribution(*, distribution, user, reason):
    """Cancela uma distribuição em rascunho ou aberta (motivo vai à auditoria)."""
    if distribution.status not in {DistributionStatus.DRAFT, DistributionStatus.OPEN}:
        raise DistributionStateError(
            "Só é possível cancelar uma distribuição em rascunho ou aberta."
        )
    if not reason or not reason.strip():
        raise DistributionStateError("Motivo obrigatório para cancelar.")
    distribution.status = DistributionStatus.CANCELED
    distribution.save(update_fields=["status", "updated_at"])
    record_event(
        action="distribution.canceled",
        entity_type="Distribution",
        entity_id=distribution.pk,
        actor=user,
        campus=distribution.campus,
        metadata={"reason": reason.strip()},
    )
    return distribution
