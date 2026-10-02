from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User, UserRole
from apps.audit.models import AuditEvent
from apps.audit.services import record_event
from apps.campus.models import Campus


class AuditPageTests(TestCase):
    def setUp(self):
        self.campus = Campus.objects.create(name="Campus Teste", code="TST")
        self.admin = User.objects.create_user(
            email="admin@example.org",
            password="x",
            name="Admin",
            campus=self.campus,
            role=UserRole.ADMIN,
        )
        self.manager = User.objects.create_user(
            email="gestor@example.org",
            password="x",
            name="Gestor",
            campus=self.campus,
            role=UserRole.MANAGER,
        )
        self.operator = User.objects.create_user(
            email="op@example.org",
            password="x",
            name="Operador",
            campus=self.campus,
            role=UserRole.OPERATOR,
        )
        record_event(
            action="distribution.opened",
            entity_type="Distribution",
            entity_id=1,
            actor=self.admin,
            campus=self.campus,
        )
        record_event(
            action="delivery.recorded",
            entity_type="Delivery",
            entity_id=9,
            actor=self.operator,
            campus=self.campus,
        )

    def test_admin_ve_auditoria(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("audit:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "distribution.opened")

    def test_gestor_pode_ver(self):
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get(reverse("audit:list")).status_code, 200)

    def test_operador_nao_pode_ver(self):
        self.client.force_login(self.operator)
        self.assertEqual(self.client.get(reverse("audit:list")).status_code, 403)

    def test_filtro_por_acao(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("audit:list"), {"action": "delivery.recorded"})
        # A tabela contém só o evento filtrado (o outro evento não aparece).
        self.assertContains(response, "Delivery#9")
        self.assertNotContains(response, "Distribution#1")
        self.assertEqual(AuditEvent.objects.count(), 2)
