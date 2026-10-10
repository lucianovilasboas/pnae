from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User, UserRole

from .models import Campus


class CampusSelectTests(TestCase):
    def setUp(self):
        self.campus = Campus.objects.create(name="Campus A", code="A")
        self.other = Campus.objects.create(name="Campus B", code="B")

    def test_operador_com_campus_nao_troca(self):
        operador = User.objects.create_user(
            email="op@example.org", password="x", name="Operador",
            campus=self.campus, role=UserRole.OPERATOR,
        )
        self.client.force_login(operador)
        page = self.client.get(reverse("campus:select"))
        self.assertContains(page, "vinculado a um campus")

        self.client.post(reverse("campus:select"), {"campus": self.other.pk})
        self.assertIsNone(self.client.session.get("campus_id"))

    def test_admin_global_escolhe_campus(self):
        admin = User.objects.create_superuser(
            email="root@example.org", password="x", name="Root"
        )
        self.client.force_login(admin)
        response = self.client.post(
            reverse("campus:select"), {"campus": self.campus.pk}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session.get("campus_id"), self.campus.pk)
