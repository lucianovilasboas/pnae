"""Regras de negócio de distribuição e entrega.

Toda operação relevante é transacional e gera `AuditEvent`. A duplicidade de
entrega regular é decidida pela constraint do banco (índice único parcial);
aqui apenas interpretamos o `IntegrityError`. Ver docs/05-testes.md.
"""

from dataclasses import dataclass

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.audit.services import record_event
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
                "turma": delivery.student.class_group.name if delivery.student.class_group else "",
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
