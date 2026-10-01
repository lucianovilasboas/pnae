import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from openpyxl import Workbook

from apps.accounts.models import User, UserRole
from apps.campus.models import Campus, ClassGroup
from apps.students.models import ImportJob, ImportJobStatus, Student

from .tokens import TOKEN_BYTES, generate_token, hash_token


class TokenTests(TestCase):
    def test_token_is_opaque_and_high_entropy(self):
        token = generate_token()
        self.assertIsInstance(token, str)
        self.assertGreaterEqual(len(token), 16)
        self.assertNotEqual(generate_token(), generate_token())

    def test_token_bytes_meets_minimum(self):
        # >= 160 bits de entropia (RN-07).
        self.assertGreaterEqual(TOKEN_BYTES * 8, 160)

    def test_hash_is_deterministic(self):
        token = "token-de-teste"
        self.assertEqual(hash_token(token), hash_token(token))

    def test_hash_differs_per_token(self):
        self.assertNotEqual(hash_token("a"), hash_token("b"))

    def test_empty_token_rejected(self):
        with self.assertRaises(ValueError):
            hash_token("")


class BaseStudentApiTests(TestCase):
    def setUp(self):
        self.campus = Campus.objects.create(name="Campus Teste", code="TST")
        self.group = ClassGroup.objects.create(
            campus=self.campus, name="1º Ano A", academic_year=2026
        )
        self.admin = User.objects.create_user(
            email="admin@example.org",
            password="x",
            name="Admin",
            campus=self.campus,
            role=UserRole.ADMIN,
        )
        self.operator = User.objects.create_user(
            email="op@example.org", password="x", name="Operador", campus=self.campus
        )


def csv_file(rows, name="alunos.csv", header="matricula;nome;turma;email"):
    content = "\n".join([header, *rows]) + "\n"
    return SimpleUploadedFile(name, content.encode("utf-8"), content_type="text/csv")


class ImportApiTests(BaseStudentApiTests):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)

    def test_preview_valida_e_nao_grava_estudantes(self):
        response = self.client.post(
            reverse("students:import-create"),
            {"file": csv_file(["2026001;Ana Silva;1º Ano A;ana@example.org", "2026002;Bruno Souza;;"])},
        )
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["validRows"], 2)
        self.assertEqual(body["rejectedRows"], 0)
        self.assertFalse(Student.objects.exists())

    def test_apply_grava_estudantes(self):
        preview = self.client.post(
            reverse("students:import-create"),
            {"file": csv_file(["2026001;Ana Silva;1º Ano A;ana@example.org"])},
        ).json()
        response = self.client.post(reverse("students:import-apply", args=[preview["id"]]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["importedRows"], 1)
        student = Student.objects.get(registration_number="2026001")
        self.assertEqual(student.full_name, "Ana Silva")
        self.assertEqual(student.class_group, self.group)

    def test_matricula_repetida_no_arquivo_e_rejeitada(self):
        response = self.client.post(
            reverse("students:import-create"),
            {"file": csv_file(["2026001;Ana Silva;;", "2026001;Ana Duplicada;;"])},
        ).json()
        self.assertEqual(response["validRows"], 1)
        self.assertEqual(response["rejectedRows"], 1)
        self.assertIn("repetida", response["errors"][0]["reason"])

    def test_turma_inexistente_e_rejeitada(self):
        response = self.client.post(
            reverse("students:import-create"),
            {"file": csv_file(["2026001;Ana Silva;Turma Fantasma;"])},
        ).json()
        self.assertEqual(response["validRows"], 0)
        self.assertIn("Turma não encontrada", response["errors"][0]["reason"])

    def test_coluna_obrigatoria_ausente_retorna_400(self):
        response = self.client.post(
            reverse("students:import-create"),
            {"file": csv_file(["2026001;Ana"], header="matricula;nome")},
        )
        # header sem a coluna 'turma' ainda é válido (turma é opcional);
        # aqui removemos o nome para forçar o erro.
        self.assertEqual(response.status_code, 201)
        response = self.client.post(
            reverse("students:import-create"),
            {"file": csv_file(["2026001"], header="matricula")},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "invalid_roster")

    def test_importacao_xlsx(self):
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(["matricula", "nome", "turma"])
        sheet.append(["2026009", "Carla Dias", "1º Ano A"])
        buffer = io.BytesIO()
        workbook.save(buffer)
        upload = SimpleUploadedFile(
            "alunos.xlsx",
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response = self.client.post(reverse("students:import-create"), {"file": upload})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["validRows"], 1)

    def test_operator_sem_permissao_recebe_403(self):
        self.client.force_login(self.operator)
        response = self.client.post(
            reverse("students:import-create"), {"file": csv_file(["2026001;Ana;;"])}
        )
        self.assertEqual(response.status_code, 403)

    def test_admin_global_usa_campus_unico(self):
        # Usuário sem campus (admin global) resolve para o único campus ativo.
        global_admin = User.objects.create_user(
            email="global@example.org",
            password="x",
            name="Global",
            role=UserRole.ADMIN,
            is_superuser=True,
        )
        self.client.force_login(global_admin)
        response = self.client.post(
            reverse("students:import-create"), {"file": csv_file(["2026001;Ana;;"])}
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["validRows"], 1)

    def test_relatorio_de_erros_em_csv(self):
        preview = self.client.post(
            reverse("students:import-create"),
            {"file": csv_file(["2026001;Ana Silva;Turma Fantasma;"])},
        ).json()
        response = self.client.get(reverse("students:import-errors", args=[preview["id"]]))
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])
        self.assertIn("motivo", response.content.decode())

    def test_apply_sem_previa_retorna_409(self):
        job = ImportJob.objects.create(
            campus=self.campus, created_by=self.admin, file_name="x.csv"
        )
        response = self.client.post(reverse("students:import-apply", args=[job.pk]))
        self.assertEqual(response.status_code, 409)


class QrExportTests(BaseStudentApiTests):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)
        self.student = Student.objects.create(
            campus=self.campus,
            registration_number="2026001",
            full_name="Ana Silva",
            class_group=self.group,
        )

    def test_export_gera_token_e_folha_imprimivel(self):
        self.assertEqual(self.student.qr_token_hash, "")
        response = self.client.post(reverse("students:qr-export"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response["Content-Type"])
        self.assertIn("data:image/png;base64,", response.content.decode())
        self.student.refresh_from_db()
        self.assertNotEqual(self.student.qr_token_hash, "")

    def test_export_rotaciona_token(self):
        self.client.post(reverse("students:qr-export"))
        self.student.refresh_from_db()
        first = self.student.qr_token_hash
        self.client.post(reverse("students:qr-export"))
        self.student.refresh_from_db()
        self.assertNotEqual(first, self.student.qr_token_hash)

    def test_only_missing_nao_toca_quem_ja_tem_token(self):
        self.client.post(reverse("students:qr-export"))
        self.student.refresh_from_db()
        before = self.student.qr_token_hash
        response = self.client.post(reverse("students:qr-export"), {"only_missing": "1"})
        self.assertEqual(response.status_code, 200)
        self.student.refresh_from_db()
        self.assertEqual(before, self.student.qr_token_hash)


class StudentPagesTests(BaseStudentApiTests):
    def test_pagina_importar_abre_para_admin(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("students_pages:import-page"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Importar estudantes")

    def test_pagina_importar_negada_para_operador(self):
        self.client.force_login(self.operator)
        response = self.client.get(reverse("students_pages:import-page"))
        self.assertEqual(response.status_code, 403)

    def test_pagina_qr_abre_para_admin(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("students_pages:qr-page"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Exportar QR Codes")
