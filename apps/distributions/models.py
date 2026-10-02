from django.db import models
from django.utils import timezone

from apps.menus.models import MealType


class DistributionStatus(models.TextChoices):
    DRAFT = "DRAFT", "Rascunho"
    OPEN = "OPEN", "Aberta"
    CLOSED = "CLOSED", "Encerrada"
    CANCELED = "CANCELED", "Cancelada"


class DeliveryType(models.TextChoices):
    REGULAR = "REGULAR", "Regular"
    EXCEDENTE = "EXCEDENTE", "Excedente"


class DeliveryStatus(models.TextChoices):
    VALIDA = "VALIDA", "Válida"
    ESTORNADA = "ESTORNADA", "Estornada"


class Distribution(models.Model):
    campus = models.ForeignKey(
        "campus.Campus",
        on_delete=models.PROTECT,
        related_name="distributions",
        verbose_name="campus",
    )
    menu = models.ForeignKey(
        "menus.Menu",
        on_delete=models.SET_NULL,
        related_name="distributions",
        verbose_name="cardápio",
        null=True,
        blank=True,
    )
    service_date = models.DateField("data do serviço")
    meal_type = models.CharField(
        "refeição", max_length=20, choices=MealType.choices, default=MealType.SNACK
    )
    planned_start_at = models.DateTimeField("início previsto")
    planned_end_at = models.DateTimeField("fim previsto")
    status = models.CharField(
        "situação",
        max_length=20,
        choices=DistributionStatus.choices,
        default=DistributionStatus.DRAFT,
    )
    estimated_quantity = models.PositiveIntegerField("quantidade prevista", null=True, blank=True)  # noqa: E501
    # Gerada em lote: reservado para abrir/encerrar automaticamente no futuro
    # (hoje a abertura/encerramento é sempre manual).
    auto_open = models.BooleanField("gerada em lote", default=False)

    extras_enabled_at = models.DateTimeField("excedentes liberados em", null=True, blank=True)
    extras_enabled_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        related_name="extras_enabled_distributions",
        verbose_name="liberou excedentes",
        null=True,
        blank=True,
    )
    opened_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        related_name="opened_distributions",
        verbose_name="abriu",
        null=True,
        blank=True,
    )
    closed_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        related_name="closed_distributions",
        verbose_name="encerrou",
        null=True,
        blank=True,
    )
    opened_at = models.DateTimeField("aberta em", null=True, blank=True)
    closed_at = models.DateTimeField("encerrada em", null=True, blank=True)
    created_at = models.DateTimeField("criada em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizada em", auto_now=True)

    class Meta:
        verbose_name = "distribuição"
        verbose_name_plural = "distribuições"
        ordering = ["-service_date", "meal_type"]
        indexes = [
            models.Index(
                fields=["campus", "service_date", "status"], name="idx_dist_campus_date_status"
            )
        ]

    def __str__(self):
        return f"{self.service_date} — {self.get_meal_type_display()} ({self.get_status_display()})"

    @property
    def can_reopen(self):
        """Encerrada e do dia de hoje (regra: reabrir só no mesmo dia)."""
        return (
            self.status == DistributionStatus.CLOSED
            and self.service_date == timezone.localdate()
        )

    # -- Transições de estado (a lógica transacional entra na Fase 2) ------
    def mark_opened(self, user):
        self.status = DistributionStatus.OPEN
        self.opened_by = user
        self.opened_at = timezone.now()

    def mark_closed(self, user):
        self.status = DistributionStatus.CLOSED
        self.closed_by = user
        self.closed_at = timezone.now()


class Delivery(models.Model):
    distribution = models.ForeignKey(
        Distribution,
        on_delete=models.PROTECT,
        related_name="deliveries",
        verbose_name="distribuição",
    )
    student = models.ForeignKey(
        "students.Student",
        on_delete=models.PROTECT,
        related_name="deliveries",
        verbose_name="estudante",
    )
    delivery_type = models.CharField("tipo", max_length=20, choices=DeliveryType.choices)
    delivered_at = models.DateTimeField("entregue em", default=timezone.now)
    recorded_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="recorded_deliveries",
        verbose_name="registrada por",
    )
    authorized_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="authorized_deliveries",
        verbose_name="autorizada por",
        null=True,
        blank=True,
    )
    reason = models.TextField("motivo", blank=True)
    status = models.CharField(
        "situação", max_length=20, choices=DeliveryStatus.choices, default=DeliveryStatus.VALIDA
    )
    reversed_at = models.DateTimeField("estornada em", null=True, blank=True)
    reversed_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="reversed_deliveries",
        verbose_name="estornada por",
        null=True,
        blank=True,
    )
    reversal_reason = models.TextField("motivo do estorno", blank=True)
    created_at = models.DateTimeField("criada em", auto_now_add=True)

    class Meta:
        verbose_name = "entrega"
        verbose_name_plural = "entregas"
        ordering = ["-delivered_at"]
        indexes = [
            models.Index(fields=["distribution", "student"], name="idx_delivery_dist_student")
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(delivery_type__in=DeliveryType.values),
                name="chk_delivery_type",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=DeliveryStatus.values),
                name="chk_delivery_status",
            ),
            # Excedente exige motivo e autorizador (RN-05).
            models.CheckConstraint(
                condition=(
                    models.Q(delivery_type=DeliveryType.REGULAR)
                    | (
                        ~models.Q(reason="")
                        & models.Q(authorized_by__isnull=False)
                    )
                ),
                name="chk_delivery_extras_requires_reason_authorizer",
            ),
        ]

    def __str__(self):
        return f"{self.delivery_type} — {self.student_id} @ {self.distribution_id}"
