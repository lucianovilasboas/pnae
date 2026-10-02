import threading
from datetime import timedelta

from django.db import IntegrityError, connection, transaction
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User, UserRole
from apps.campus.models import Campus, ClassGroup
from apps.students.models import Student
from apps.students.tokens import generate_token, hash_token

from . import services
from .models import (
    Delivery,
    DeliveryStatus,
    DeliveryType,
    Distribution,
    DistributionStatus,
)


def make_student(campus, group, registration, name, token=None, active=True):
    student = Student.objects.create(
        campus=campus,
        registration_number=registration,
        full_name=name,
        class_group=group,
        active=active,
    )
    if token is not None:
        student.qr_token_hash = hash_token(token)
        student.save(update_fields=["qr_token_hash"])
    return student


class DistributionFixture(TestCase):
    def setUp(self):
        self.campus = Campus.objects.create(name="Campus Teste", code="TST")
        self.group = ClassGroup.objects.create(
            campus=self.campus, name="1º Ano A", academic_year=2026
        )
        self.operator = User.objects.create_user(
            email="op@example.org",
            password="x",
            name="Operador",
            campus=self.campus,
            role=UserRole.OPERATOR,
        )
        self.authorizer = User.objects.create_user(
            email="auth@example.org",
            password="x",
            name="Autorizador",
            campus=self.campus,
            role=UserRole.ADMIN,
            can_authorize_extras=True,
            can_reverse_deliveries=True,
        )
        self.token = generate_token()
        self.student = make_student(
            self.campus, self.group, "2026001", "Ana Silva", token=self.token
        )
        self.distribution = Distribution.objects.create(
            campus=self.campus,
            service_date=timezone.localdate(),
            meal_type="LUNCH",
            planned_start_at=timezone.now(),
            planned_end_at=timezone.now(),
            status=DistributionStatus.OPEN,
        )


class PartialUniqueIndexTests(DistributionFixture):
    """Regra garantida pelo banco, não só pela aplicação."""

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
            reason="Segunda refeição",
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


class ScanServiceTests(DistributionFixture):
    def scan(self, token=None):
        return services.record_scan(
            distribution=self.distribution,
            token=self.token if token is None else token,
            user=self.operator,
        )

    def test_entrega_regular(self):
        result = self.scan()
        self.assertEqual(result.result, "DELIVERED")
        self.assertEqual(result.student, self.student)
        self.assertEqual(
            Delivery.objects.filter(
                distribution=self.distribution,
                delivery_type=DeliveryType.REGULAR,
                status=DeliveryStatus.VALIDA,
            ).count(),
            1,
        )

    def test_duplicidade_retorna_already_delivered(self):
        self.scan()
        result = self.scan()
        self.assertEqual(result.result, "ALREADY_DELIVERED")
        self.assertIsNotNone(result.previous_delivery)
        self.assertEqual(
            Delivery.objects.filter(
                distribution=self.distribution, delivery_type=DeliveryType.REGULAR
            ).count(),
            1,
        )

    def test_qr_invalido(self):
        self.assertEqual(self.scan("token-inexistente").result, "INVALID_TOKEN")

    def test_distribuicao_fechada(self):
        self.distribution.status = DistributionStatus.CLOSED
        self.distribution.save()
        self.assertEqual(self.scan().result, "DISTRIBUTION_CLOSED")

    def test_estudante_inativo_e_inelegivel(self):
        self.student.active = False
        self.student.save()
        self.assertEqual(self.scan().result, "INELIGIBLE")

    def test_summary_conta_pendentes(self):
        self.scan()
        summary = services.distribution_summary(self.distribution)
        self.assertEqual(summary["eligible"], 1)
        self.assertEqual(summary["regularValid"], 1)
        self.assertEqual(summary["pending"], 0)

    def test_estorno_libera_nova_entrega_e_preserva_original(self):
        result = self.scan()
        services.reverse_delivery(delivery=result.delivery, reason="Erro", user=self.authorizer)
        original = Delivery.objects.get(pk=result.delivery.pk)
        self.assertEqual(original.status, DeliveryStatus.ESTORNADA)
        self.assertEqual(self.scan().result, "DELIVERED")

    def test_excedente_exige_motivo(self):
        with self.assertRaises(services.DistributionStateError):
            services.register_extra(
                distribution=self.distribution,
                student=self.student,
                reason="",
                recorded_by=self.operator,
                authorized_by=self.authorizer,
            )

    def test_ciclo_de_vida(self):
        draft = services.create_distribution(
            campus=self.campus,
            user=self.operator,
            service_date=timezone.localdate() + timedelta(days=1),
            meal_type="DINNER",
            planned_start_at=timezone.now(),
            planned_end_at=timezone.now(),
        )
        self.assertEqual(draft.status, DistributionStatus.DRAFT)
        services.open_distribution(distribution=draft, user=self.operator)
        self.assertEqual(draft.status, DistributionStatus.OPEN)
        services.close_distribution(distribution=draft, user=self.operator)
        self.assertEqual(draft.status, DistributionStatus.CLOSED)
        with self.assertRaises(services.DistributionStateError):
            services.close_distribution(distribution=draft, user=self.operator)


class ScanApiTests(DistributionFixture):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.operator)
        self.url = reverse("distributions_api:scan", args=[self.distribution.pk])

    def _scan(self, token):
        return self.client.post(
            self.url, data={"token": token}, content_type="application/json"
        )

    def test_scan_delivered(self):
        response = self._scan(self.token)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["result"], "DELIVERED")
        self.assertEqual(body["student"]["registrationNumber"], "2026001")
        # Nenhum campo devolve o token bruto.
        self.assertNotIn("token", [key.lower() for key in body])

    def test_scan_duplicado(self):
        self._scan(self.token)
        self.assertEqual(self._scan(self.token).json()["result"], "ALREADY_DELIVERED")

    def test_summary_endpoint(self):
        self._scan(self.token)
        response = self.client.get(
            reverse("distributions_api:summary", args=[self.distribution.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["regularValid"], 1)

    def test_manager_nao_pode_escanear(self):
        manager = User.objects.create_user(
            email="gestor@example.org",
            password="x",
            name="Gestor",
            campus=self.campus,
            role=UserRole.MANAGER,
        )
        self.client.force_login(manager)
        self.assertEqual(self._scan(self.token).status_code, 403)


class ConcurrentScanTests(TransactionTestCase):
    """Duas leituras simultâneas do mesmo QR → exatamente uma entrega regular."""

    def setUp(self):
        self.campus = Campus.objects.create(name="Campus Conc", code="CONC")
        self.group = ClassGroup.objects.create(
            campus=self.campus, name="1º Ano A", academic_year=2026
        )
        self.operator = User.objects.create_user(
            email="op@example.org",
            password="x",
            name="Operador",
            campus=self.campus,
            role=UserRole.OPERATOR,
        )
        self.token = generate_token()
        self.student = make_student(
            self.campus, self.group, "2026001", "Ana Silva", token=self.token
        )
        self.distribution = Distribution.objects.create(
            campus=self.campus,
            service_date=timezone.localdate(),
            meal_type="LUNCH",
            planned_start_at=timezone.now(),
            planned_end_at=timezone.now(),
            status=DistributionStatus.OPEN,
        )

    def test_duas_leituras_concorrentes_geram_uma_entrega(self):
        results = []
        barrier = threading.Barrier(2)

        def worker():
            connection.close()
            barrier.wait()
            result = services.record_scan(
                distribution=self.distribution, token=self.token, user=self.operator
            )
            results.append(result.result)
            connection.close()

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(sorted(results), ["ALREADY_DELIVERED", "DELIVERED"])
        self.assertEqual(
            Delivery.objects.filter(
                distribution=self.distribution,
                student=self.student,
                delivery_type=DeliveryType.REGULAR,
                status=DeliveryStatus.VALIDA,
            ).count(),
            1,
        )


class ReportTests(DistributionFixture):
    def _scan(self, token=None):
        return services.record_scan(
            distribution=self.distribution,
            token=self.token if token is None else token,
            user=self.operator,
        )

    def test_relatorio_reconcilia_regular_excedente_estorno(self):
        self._scan()
        services.register_extra(
            distribution=self.distribution,
            student=self.student,
            reason="Segunda refeição",
            recorded_by=self.authorizer,
            authorized_by=self.authorizer,
        )
        token2 = generate_token()
        s2 = make_student(self.campus, self.group, "2026002", "Bruno Souza", token=token2)
        self._scan(token2)
        d2 = Delivery.objects.get(distribution=self.distribution, student=s2)
        services.reverse_delivery(delivery=d2, reason="Erro de leitura", user=self.authorizer)

        report = services.distribution_report(self.distribution)
        self.assertEqual(report["summary"]["regularValid"], 1)
        self.assertEqual(report["summary"]["extrasValid"], 1)
        self.assertEqual(report["summary"]["reversed"], 1)
        self.assertEqual(report["regular"].count(), 1)
        self.assertEqual(report["extras"].count(), 1)
        self.assertEqual(report["reversed_deliveries"].count(), 1)
        self.assertEqual(report["by_class"][0]["regular"], 1)

        rows = services.report_rows(self.distribution)
        self.assertEqual(len(rows), 3)  # 1 regular válida + 1 excedente + 1 estornada

    def test_api_report_json_e_csv(self):
        self.client.force_login(self.operator)
        self._scan()
        url = reverse("distributions_api:report", args=[self.distribution.pk])
        body = self.client.get(url).json()
        self.assertEqual(body["summary"]["regularValid"], 1)
        self.assertEqual(body["counts"]["regular"], 1)

        response = self.client.get(url + "?format=csv")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])
        self.assertIn("matricula;nome", response.content.decode())

    def test_pagina_relatorio_csv(self):
        self.client.force_login(self.operator)
        self._scan()
        response = self.client.get(
            reverse("distributions:report-csv", args=[self.distribution.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Ana Silva", response.content.decode())


class DeliveriesPageTests(DistributionFixture):
    def setUp(self):
        super().setUp()
        self.result = services.record_scan(
            distribution=self.distribution, token=self.token, user=self.operator
        )
        self.url = reverse("distributions:deliveries", args=[self.distribution.pk])

    def test_estorno_pela_pagina(self):
        self.client.force_login(self.authorizer)
        response = self.client.post(
            self.url,
            {"action": "reverse", "delivery_id": self.result.delivery.pk, "reason": "Erro"},
        )
        self.assertEqual(response.status_code, 302)
        self.result.delivery.refresh_from_db()
        self.assertEqual(self.result.delivery.status, DeliveryStatus.ESTORNADA)

    def test_operador_sem_permissao_nao_estorna(self):
        self.client.force_login(self.operator)  # sem can_reverse
        self.client.post(
            self.url,
            {"action": "reverse", "delivery_id": self.result.delivery.pk, "reason": "x"},
        )
        self.result.delivery.refresh_from_db()
        self.assertEqual(self.result.delivery.status, DeliveryStatus.VALIDA)


class PilotDrillTests(TestCase):
    def setUp(self):
        self.campus = Campus.objects.create(name="Campus Drill", code="DRL")
        User.objects.create_superuser(
            email="root@example.org", password="x", name="Root", campus=self.campus
        )

    def test_drill_encerra_coerente(self):
        from django.core.management import call_command

        call_command(
            "pilot_drill",
            "--campus",
            "DRL",
            "--students",
            "55",
            "--duplicates",
            "10",
            "--extras",
            "3",
            "--reversals",
            "2",
        )
        distribution = Distribution.objects.get(campus=self.campus, meal_type="SNACK")
        self.assertEqual(distribution.status, DistributionStatus.CLOSED)
        summary = services.distribution_summary(distribution)
        self.assertEqual(summary["regularValid"], 55 - 2)
        self.assertEqual(summary["extrasValid"], 3)
        self.assertEqual(summary["reversed"], 2)
        self.assertEqual(
            Delivery.objects.filter(distribution=distribution, delivery_type=DeliveryType.REGULAR).count(),
            55,
        )


class OperationCameraTests(DistributionFixture):
    def test_pagina_operacao_traz_camera_zxing(self):
        self.client.force_login(self.operator)
        response = self.client.get(reverse("distributions:operation", args=[self.distribution.pk]))
        self.assertContains(response, "vendor/zxing/zxing-browser.min.js")
        self.assertContains(response, 'id="cam-toggle"')
        self.assertContains(response, 'id="cam-switch"')

    def test_arquivo_zxing_esta_disponivel(self):
        from django.contrib.staticfiles import finders

        self.assertIsNotNone(finders.find("vendor/zxing/zxing-browser.min.js"))


class MobileUiTests(DistributionFixture):
    def test_cabecalho_tem_menu_hamburguer(self):
        self.client.force_login(self.operator)
        response = self.client.get(reverse("distributions:home"))
        self.assertContains(response, 'id="nav-menu"')
        self.assertContains(response, "menu-toggle")
        self.assertContains(response, "Cardápios")

    def test_operacao_tem_placeholder_e_icone(self):
        self.client.force_login(self.operator)
        response = self.client.get(
            reverse("distributions:operation", args=[self.distribution.pk])
        )
        self.assertContains(response, 'id="cam-placeholder"')
        self.assertContains(response, 'id="feedback-icon"')
        self.assertContains(response, "vendor/zxing/zxing-browser.min.js")
