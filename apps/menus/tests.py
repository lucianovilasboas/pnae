from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User, UserRole
from apps.audit.models import AuditEvent
from apps.campus.models import Campus
from apps.distributions.models import Distribution
from apps.menus.models import MealType, Menu


class MenuPageTests(TestCase):
    def setUp(self):
        self.campus = Campus.objects.create(name="Campus Teste", code="TST")
        self.admin = User.objects.create_user(
            email="admin@example.org", password="x", name="Admin",
            campus=self.campus, role=UserRole.ADMIN,
        )
        self.operator = User.objects.create_user(
            email="op@example.org", password="x", name="Operador",
            campus=self.campus, role=UserRole.OPERATOR,
        )
        self.manager = User.objects.create_user(
            email="gestor@example.org", password="x", name="Gestor",
            campus=self.campus, role=UserRole.MANAGER,
        )

    def test_cria_cardapio_pela_pagina(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("menus:list"),
            {
                "service_date": str(timezone.localdate()),
                "meal_type": "SNACK",
                "description": "Pão com mortadela e suco",
            },
        )
        self.assertEqual(response.status_code, 302)
        menu = Menu.objects.get()
        self.assertEqual(menu.campus, self.campus)
        self.assertEqual(menu.meal_type, MealType.SNACK)
        self.assertTrue(AuditEvent.objects.filter(action="menu.created").exists())

    def test_refeicao_padrao_e_lanche(self):
        self.client.force_login(self.admin)
        self.client.post(
            reverse("menus:list"),
            {"service_date": str(timezone.localdate()), "description": "Fruta"},
        )
        self.assertEqual(Menu.objects.get().meal_type, MealType.SNACK)

    def test_operador_pode_cadastrar(self):
        self.client.force_login(self.operator)
        self.assertEqual(self.client.get(reverse("menus:list")).status_code, 200)

    def test_gestor_nao_pode(self):
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get(reverse("menus:list")).status_code, 403)


class DistributionMenuTests(TestCase):
    def setUp(self):
        self.campus = Campus.objects.create(name="Campus Teste", code="TST")
        self.operator = User.objects.create_user(
            email="op@example.org", password="x", name="Operador",
            campus=self.campus, role=UserRole.OPERATOR,
        )
        self.menu = Menu.objects.create(
            campus=self.campus, service_date=timezone.localdate(),
            meal_type=MealType.SNACK, description="Lanche", created_by=self.operator,
        )

    def test_distribuicao_vincula_cardapio(self):
        self.client.force_login(self.operator)
        self.client.post(
            reverse("distributions:list"),
            {
                "action": "create",
                "service_date": str(timezone.localdate()),
                "meal_type": "SNACK",
                "menu": self.menu.pk,
                "planned_start_at": "2026-10-02T15:00",
                "planned_end_at": "2026-10-02T16:00",
            },
        )
        distribution = Distribution.objects.get()
        self.assertEqual(distribution.menu, self.menu)
        self.assertEqual(distribution.meal_type, MealType.SNACK)
