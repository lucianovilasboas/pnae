from datetime import timedelta

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User, UserRole
from apps.campus.models import Campus, ClassGroup
from apps.menus.models import MealType, Menu
from apps.students.models import Student, StudentAccount

from . import services

PASSWORD = "Estudante#2026"
CPF = "703.246.516-19"


class PortalFixture(TestCase):
    def setUp(self):
        cache.clear()
        self.campus = Campus.objects.create(name="Campus Teste", code="TST")
        self.group = ClassGroup.objects.create(
            campus=self.campus, name="1º Ano A", academic_year=2026
        )
        self.student = Student.objects.create(
            campus=self.campus,
            registration_number="2026001",
            full_name="Ana Silva",
            email="ana@example.org",
            cpf=CPF,
            class_group=self.group,
        )

    def _first_access(self, **overrides):
        data = {
            "registration_number": "2026001",
            "cpf": CPF,
            "password": PASSWORD,
            "password2": PASSWORD,
        }
        data.update(overrides)
        return self.client.post(reverse("portal:first-access"), data)


class FirstAccessTests(PortalFixture):
    def test_cria_conta_e_loga(self):
        response = self._first_access()
        self.assertRedirects(response, reverse("portal:dashboard"))
        account = StudentAccount.objects.get(student=self.student)
        self.assertEqual(account.email, "ana@example.org")
        self.assertTrue(account.check_password(PASSWORD))
        self.assertEqual(self.client.session["portal_account_id"], account.pk)

    def test_cpf_errado_nao_cria(self):
        self._first_access(cpf="000.000.000-00")
        self.assertFalse(StudentAccount.objects.exists())

    def test_matricula_inexistente_nao_cria(self):
        self._first_access(registration_number="9999999")
        self.assertFalse(StudentAccount.objects.exists())

    def test_senha_curta_rejeitada(self):
        self._first_access(password="123", password2="123")
        self.assertFalse(StudentAccount.objects.exists())

    def test_senhas_diferentes_rejeitadas(self):
        self._first_access(password2="OutraSenha#1")
        self.assertFalse(StudentAccount.objects.exists())

    def test_aluno_sem_email_nao_cria(self):
        self.student.email = ""
        self.student.save(update_fields=["email"])
        self._first_access()
        self.assertFalse(StudentAccount.objects.exists())

    def test_conta_ja_existente(self):
        self._first_access()
        self._first_access()
        self.assertEqual(StudentAccount.objects.count(), 1)


class LoginTests(PortalFixture):
    def setUp(self):
        super().setUp()
        self._first_access()
        self.client.post(reverse("portal:logout"))

    def test_login_ok(self):
        response = self.client.post(
            reverse("portal:login"), {"email": "ana@example.org", "password": PASSWORD}
        )
        self.assertRedirects(response, reverse("portal:dashboard"))

    def test_login_senha_errada(self):
        self.client.post(
            reverse("portal:login"), {"email": "ana@example.org", "password": "errada123"}
        )
        self.assertNotIn("portal_account_id", self.client.session)

    def test_login_aluno_inativo_negado(self):
        self.student.active = False
        self.student.save(update_fields=["active"])
        self.client.post(
            reverse("portal:login"), {"email": "ana@example.org", "password": PASSWORD}
        )
        self.assertNotIn("portal_account_id", self.client.session)

    def test_throttle_apos_muitas_tentativas(self):
        for _ in range(10):
            self.client.post(
                reverse("portal:login"), {"email": "ana@example.org", "password": "x12345678"}
            )
        response = self.client.post(
            reverse("portal:login"), {"email": "ana@example.org", "password": PASSWORD}
        )
        self.assertEqual(response.status_code, 200)  # bloqueado, não redireciona
        self.assertNotIn("portal_account_id", self.client.session)


class RecoverTests(PortalFixture):
    def test_recupera_senha(self):
        self._first_access()
        self.client.post(reverse("portal:logout"))
        response = self.client.post(
            reverse("portal:recover"),
            {
                "registration_number": "2026001",
                "cpf": CPF,
                "password": "NovaSenha#2026",
                "password2": "NovaSenha#2026",
            },
        )
        self.assertRedirects(response, reverse("portal:login"))
        account = StudentAccount.objects.get()
        self.assertTrue(account.check_password("NovaSenha#2026"))

    def test_recupera_sem_conta_falha(self):
        self.client.post(
            reverse("portal:recover"),
            {
                "registration_number": "2026001",
                "cpf": CPF,
                "password": "NovaSenha#2026",
                "password2": "NovaSenha#2026",
            },
        )
        self.assertFalse(StudentAccount.objects.exists())


class SessionIsolationTests(PortalFixture):
    def test_staff_nao_acessa_painel(self):
        response = self.client.get(reverse("portal:dashboard"))
        self.assertRedirects(response, reverse("portal:login"))

    def test_aluno_nao_acessa_area_staff(self):
        self._first_access()
        response = self.client.get(reverse("distributions:list"))
        # request.user continua anônimo; a área da equipe manda para o login dela.
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response["Location"])

    def test_logout_encerra_sessao(self):
        self._first_access()
        response = self.client.post(reverse("portal:logout"))
        self.assertRedirects(response, reverse("portal:login"))
        self.assertNotIn("portal_account_id", self.client.session)


class PortalContentTests(PortalFixture):
    def setUp(self):
        super().setUp()
        self._first_access()
        self.today = timezone.localdate()
        self.author = User.objects.create_user(
            email="autor@example.org", password="x", name="Autor",
            campus=self.campus, role=UserRole.ADMIN,
        )

    def _menu(self, day, description, published=True):
        return Menu.objects.create(
            campus=self.campus, service_date=day, meal_type=MealType.SNACK,
            description=description, created_by=self.author, published=published,
        )

    def test_painel_mostra_publicado_e_esconde_rascunho(self):
        self._menu(self.today, "Lanche publicado", published=True)
        self._menu(self.today + timedelta(days=1), "Rascunho", published=False)
        body = self.client.get(reverse("portal:dashboard")).content.decode()
        self.assertIn("Lanche publicado", body)
        self.assertNotIn("Rascunho", body)

    def test_painel_escopo_de_campus(self):
        other = Campus.objects.create(name="Campus Outro", code="OUT")
        Menu.objects.create(
            campus=other, service_date=self.today, meal_type=MealType.SNACK,
            description="De outro campus", created_by=self.author, published=True,
        )
        body = self.client.get(reverse("portal:dashboard")).content.decode()
        self.assertNotIn("De outro campus", body)

    def test_semana_so_publicados(self):
        self._menu(self.today, "Segunda publicada")
        body = self.client.get(reverse("portal:week")).content.decode()
        self.assertIn("Cardápio da semana", body)
        self.assertIn("Segunda publicada", body)

    def test_qr_mostra_matricula_e_no_store(self):
        response = self.client.get(reverse("portal:qr"))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn("2026001", body)
        self.assertIn("data:image/png;base64,", body)
        self.assertEqual(response["Cache-Control"], "no-store")
