from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User, UserRole
from apps.campus.models import Campus, ClassGroup
from apps.students.models import Student

from .models import Delivery, DeliveryStatus, DeliveryType, Distribution, DistributionStatus


class PartialUniqueIndexTests(TestCase):
    """Prova que a regra de entrega regular única é garantida pelo banco
    (índice único parcial), e não apenas pela aplicação. Ver docs/05-testes.md.
    """

    def setUp(self):
        self.campus = Campus.objects.create(name="Campus Teste", code="TST")
        self.group = ClassGroup.objects.create(
            campus=self.campus, name="1º Ano A", academic_year=2026
        )
        self.operator = User.objects.create_user(
            email="op@example.org", password="x", name="Operador", campus=self.campus
        )
        self.authorizer = User.objects.create_user(
            email="auth@example.org",
            password="x",
            name="Autorizador",
            campus=self.campus,
            role=UserRole.ADMIN,
            can_authorize_extras=True,
        )
        self.student = Student.objects.create(
            campus=self.campus,
            registration_number="2026001",
            full_name="Estudante Teste",
            class_group=self.group,
        )
        self.distribution = Distribution.objects.create(
            campus=self.campus,
            service_date=timezone.localdate(),
            meal_type="LUNCH",
            planned_start_at=timezone.now(),
            planned_end_at=timezone.now(),
            status=DistributionStatus.OPEN,
        )

    def _delivery(self, **kwargs):
        defaults = {
            "distribution": self.distribution,
            "student": self.student,
            "delivery_type": DeliveryType.REGULAR,
            "recorded_by": self.operator,
        }
        defaults.update(kwargs)
        return Delivery.objects.create(**defaults)

    def test_segunda_regular_valida_e_bloqueada_pelo_banco(self):
        self._delivery()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._delivery()

    def test_excedente_autorizado_coexiste_com_a_regular(self):
        self._delivery()
        extra = self._delivery(
            delivery_type=DeliveryType.EXCEDENTE,
            reason="Segunda refeição autorizada",
            authorized_by=self.authorizer,
        )
        self.assertEqual(extra.status, DeliveryStatus.VALIDA)

    def test_excedente_sem_motivo_e_autorizador_e_rejeitado(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._delivery(delivery_type=DeliveryType.EXCEDENTE)

    def test_nova_regular_liberada_apos_estorno(self):
        first = self._delivery()
        first.status = DeliveryStatus.ESTORNADA
        first.reversed_at = timezone.now()
        first.reversed_by = self.authorizer
        first.reversal_reason = "Leitura indevida"
        first.save()
        # O índice parcial libera nova entrega regular para o mesmo estudante.
        second = self._delivery()
        self.assertEqual(second.status, DeliveryStatus.VALIDA)

    def test_uma_unica_distribuicao_aberta_por_campus_data_refeicao(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Distribution.objects.create(
                campus=self.campus,
                service_date=self.distribution.service_date,
                meal_type=self.distribution.meal_type,
                planned_start_at=timezone.now(),
                planned_end_at=timezone.now(),
                status=DistributionStatus.OPEN,
            )
