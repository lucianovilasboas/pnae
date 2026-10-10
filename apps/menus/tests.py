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
                "inicio": "15:00",
                "fim": "16:00",
            },
        )
        distribution = Distribution.objects.get()
        self.assertEqual(distribution.menu, self.menu)
        self.assertEqual(distribution.meal_type, MealType.SNACK)
        # A hora é combinada com a data escolhida (fuso local).
        self.assertEqual(
            timezone.localtime(distribution.planned_start_at).strftime("%H:%M"),
            "15:00",
        )

    def test_cardapio_retorna_para_distribuicao(self):
        """O formulário de cardápio volta à distribuição quando recebe `voltar`."""
        self.client.force_login(self.operator)
        # Data diferente do cardápio do setUp (hoje), pela unicidade campus+data+refeição.
        destino = reverse("distributions:list") + "?data=2026-10-11&refeicao=SNACK#nova"
        response = self.client.post(
            reverse("menus:list"),
            {
                "service_date": "2026-10-11",
                "meal_type": "SNACK",
                "description": "Lanche do dia",
                "voltar": destino,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], destino)
        self.assertTrue(Menu.objects.filter(description="Lanche do dia").exists())

    def test_gestor_nao_retorna_para_url_externa(self):
        """`voltar` só aceita destino interno (sem open redirect)."""
        self.client.force_login(self.operator)
        response = self.client.post(
            reverse("menus:list"),
            {
                "service_date": "2026-10-11",
                "meal_type": "SNACK",
                "description": "Lanche",
                "voltar": "https://evil.example.org/",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("menus:list"))


class BulkMenuTests(TestCase):
    def setUp(self):
        self.campus = Campus.objects.create(name="Campus Teste", code="TST")
        self.operator = User.objects.create_user(
            email="op@example.org", password="x", name="Operador",
            campus=self.campus, role=UserRole.OPERATOR,
        )

    def test_bulk_menus_cria_e_pula(self):
        from datetime import date

        from .services import create_menus_bulk

        result = create_menus_bulk(
            campus=self.campus, user=self.operator,
            start_date=date(2026, 10, 1), end_date=date(2026, 10, 7),
            weekdays={0, 1, 2, 3, 4}, meal_type="SNACK", description="Lanche X",
        )
        self.assertEqual(result["created"], 5)  # Seg–Sex
        self.assertEqual(Menu.objects.filter(description="Lanche X").count(), 5)

        again = create_menus_bulk(
            campus=self.campus, user=self.operator,
            start_date=date(2026, 10, 1), end_date=date(2026, 10, 7),
            weekdays={0, 1, 2, 3, 4}, meal_type="SNACK", description="Lanche X",
        )
        self.assertEqual(again["created"], 0)
        self.assertEqual(again["skipped"], 5)


class MenuPublishTests(TestCase):
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

    def _post(self, action, menu=None):
        return self.client.post(
            reverse("menus:list"),
            {"action": action, "id": (menu or self.menu).pk},
        )

    def test_publica_e_audita(self):
        self.client.force_login(self.operator)
        self.assertFalse(self.menu.published)
        response = self._post("publish")
        self.assertEqual(response.status_code, 302)
        self.menu.refresh_from_db()
        self.assertTrue(self.menu.published)
        self.assertIsNotNone(self.menu.published_at)
        self.assertEqual(self.menu.published_by, self.operator)
        self.assertTrue(AuditEvent.objects.filter(action="menu.published").exists())

    def test_despublica(self):
        self.client.force_login(self.operator)
        self._post("publish")
        self._post("unpublish")
        self.menu.refresh_from_db()
        self.assertFalse(self.menu.published)
        self.assertIsNone(self.menu.published_by)
        self.assertTrue(AuditEvent.objects.filter(action="menu.unpublished").exists())

    def test_nao_publica_cardapio_de_outro_campus(self):
        other = Campus.objects.create(name="Campus Outro", code="OUT")
        outro = Menu.objects.create(
            campus=other, service_date=timezone.localdate(),
            meal_type=MealType.SNACK, description="Outro", created_by=self.operator,
        )
        self.client.force_login(self.operator)
        self._post("publish", menu=outro)
        outro.refresh_from_db()
        self.assertFalse(outro.published)


class MenuEditDeleteTests(TestCase):
    def setUp(self):
        from datetime import timedelta

        from django.utils import timezone

        from apps.distributions.models import Distribution, DistributionStatus

        self.campus = Campus.objects.create(name="Campus Teste", code="TST")
        self.operator = User.objects.create_user(
            email="op@example.org", password="x", name="Operador",
            campus=self.campus, role=UserRole.OPERATOR,
        )
        self.menu = Menu.objects.create(
            campus=self.campus, service_date=timezone.localdate(),
            meal_type=MealType.SNACK, description="Lanche", created_by=self.operator,
        )
        self.tomorrow = timezone.localdate() + timedelta(days=1)
        self.now = timezone.now()
        self.Distribution = Distribution
        self.DistributionStatus = DistributionStatus

    def test_edita_cardapio(self):
        from .services import update_menu

        update_menu(
            menu=self.menu, user=self.operator, service_date=self.menu.service_date,
            meal_type=MealType.SNACK, description="Novo lanche", notes="obs",
        )
        self.menu.refresh_from_db()
        self.assertEqual(self.menu.description, "Novo lanche")

    def test_editar_conflito_unico(self):
        from .services import MenuStateError, update_menu

        outro = Menu.objects.create(
            campus=self.campus, service_date=self.tomorrow,
            meal_type=MealType.SNACK, description="Outro", created_by=self.operator,
        )
        with self.assertRaises(MenuStateError):
            update_menu(
                menu=outro, user=self.operator, service_date=self.menu.service_date,
                meal_type=MealType.SNACK, description="Conflito",
            )

    def test_nao_exclui_cardapio_vinculado(self):
        from .services import MenuStateError, delete_menu

        self.Distribution.objects.create(
            campus=self.campus, menu=self.menu, service_date=self.menu.service_date,
            meal_type=self.menu.meal_type, planned_start_at=self.now,
            planned_end_at=self.now, status=self.DistributionStatus.DRAFT,
        )
        with self.assertRaises(MenuStateError):
            delete_menu(menu=self.menu, user=self.operator)

    def test_exclui_cardapio_sem_vinculo(self):
        from .services import delete_menu

        pk = self.menu.pk
        delete_menu(menu=self.menu, user=self.operator)
        self.assertFalse(Menu.objects.filter(pk=pk).exists())


class MenuApiTests(TestCase):
    """Criação de cardápio único pelo pop-up da tela de distribuições."""

    def setUp(self):
        self.campus = Campus.objects.create(name="Campus Teste", code="TST")
        self.operator = User.objects.create_user(
            email="op@example.org", password="x", name="Operador",
            campus=self.campus, role=UserRole.OPERATOR,
        )
        self.url = reverse("menus_api:create")

    def _post(self, **kw):
        return self.client.post(self.url, data=kw, content_type="application/json")

    def test_cria_cardapio_json(self):
        self.client.force_login(self.operator)
        response = self._post(
            service_date="2026-10-20", meal_type="SNACK", description="Lanche"
        )
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["mealType"], "SNACK")
        self.assertIn("label", body)
        self.assertTrue(Menu.objects.filter(campus=self.campus, description="Lanche").exists())

    def test_duplicado_retorna_409(self):
        self.client.force_login(self.operator)
        self._post(service_date="2026-10-20", meal_type="SNACK", description="Lanche")
        response = self._post(
            service_date="2026-10-20", meal_type="SNACK", description="Outro"
        )
        self.assertEqual(response.status_code, 409)

    def test_sem_descricao_retorna_400(self):
        self.client.force_login(self.operator)
        response = self._post(service_date="2026-10-20", meal_type="SNACK", description="")
        self.assertEqual(response.status_code, 400)

    def test_admin_global_informa_campus(self):
        Campus.objects.create(name="Outro", code="OUT")  # 2º campus ativo → ambíguo
        admin = User.objects.create_superuser(
            email="root@example.org", password="x", name="Root"
        )
        self.client.force_login(admin)
        response = self._post(
            service_date="2026-10-21", meal_type="SNACK",
            description="Via campus explícito", campus=self.campus.pk,
        )
        self.assertEqual(response.status_code, 201)

    def test_gestor_nao_pode(self):
        manager = User.objects.create_user(
            email="gestor@example.org", password="x", name="Gestor",
            campus=self.campus, role=UserRole.MANAGER,
        )
        self.client.force_login(manager)
        response = self._post(service_date="2026-10-20", meal_type="SNACK", description="X")
        self.assertEqual(response.status_code, 403)
