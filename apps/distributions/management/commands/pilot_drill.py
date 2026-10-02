"""Ensaio operacional: simula uma sessão de distribuição com volume.

Cria estudantes sintéticos (prefixo DRILL-), gera tokens, executa leituras
(incluindo duplicidades, excedente e estorno) e confere a coerência dos totais.
Não toca nos token/QR dos estudantes reais.

Exemplo:
    python manage.py pilot_drill --campus PN --students 60
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.campus.models import Campus, ClassGroup
from apps.campus.selectors import resolve_campus
from apps.distributions import services
from apps.distributions.models import DeliveryStatus, DeliveryType
from apps.menus.models import MealType
from apps.students import qr
from apps.students.models import Student

DRILL_GROUP = "DRILL"


class Command(BaseCommand):
    help = "Ensaio de distribuição com N leituras simuladas e verificação de totais."

    def add_arguments(self, parser):
        parser.add_argument("--campus", default="", help="código do campus")
        parser.add_argument("--students", type=int, default=60, help="quantos estudantes simular")
        parser.add_argument("--duplicates", type=int, default=10, help="releituras (duplicidade)")
        parser.add_argument("--extras", type=int, default=3, help="excedentes autorizados")
        parser.add_argument("--reversals", type=int, default=2, help="estornos")
        parser.add_argument("--cleanup", action="store_true", help="remove os dados do ensaio ao fim")

    def handle(self, *args, **options):
        count = options["students"]
        if count < 1:
            raise CommandError("--students deve ser >= 1.")

        campus = self._resolve_campus(options)
        operator = self._resolve_user()
        group, _ = ClassGroup.objects.get_or_create(
            campus=campus,
            name=DRILL_GROUP,
            academic_year=timezone.localdate().year,
            defaults={"course": "Ensaio"},
        )
        students = self._ensure_students(campus, group, count)

        distribution = services.create_distribution(
            campus=campus,
            user=operator,
            service_date=timezone.localdate(),
            meal_type=MealType.OTHER,
            planned_start_at=timezone.now(),
            planned_end_at=timezone.now(),
        )
        services.open_distribution(distribution=distribution, user=operator)

        # 1. Uma leitura por estudante.
        tokens = {}
        delivered = 0
        for student in students:
            _, tokens[student.pk] = qr.assign_tokens([student])[0]
            result = services.record_scan(
                distribution=distribution, token=tokens[student.pk], user=operator
            )
            if result.result == "DELIVERED":
                delivered += 1

        # 2. Releitura do mesmo QR — deve ser barrada como duplicidade.
        duplicate_hits = 0
        for student in students[: options["duplicates"]]:
            if services.record_scan(
                distribution=distribution, token=tokens[student.pk], user=operator
            ).result == "ALREADY_DELIVERED":
                duplicate_hits += 1

        # 3. Excedentes autorizados.
        extras = 0
        for student in students[: options["extras"]]:
            services.register_extra(
                distribution=distribution,
                student=student,
                reason="Ensaio operacional",
                recorded_by=operator,
                authorized_by=operator,
            )
            extras += 1

        # 4. Estornos.
        reversals = 0
        for delivery in distribution.deliveries.filter(
            status=DeliveryStatus.VALIDA, delivery_type=DeliveryType.REGULAR
        )[: options["reversals"]]:
            services.reverse_delivery(
                delivery=delivery, reason="Ensaio operacional", user=operator
            )
            reversals += 1

        services.close_distribution(distribution=distribution, user=operator)
        summary = services.distribution_summary(distribution)

        expected_regular = delivered - reversals
        ok = (
            summary["regularValid"] == expected_regular
            and summary["extrasValid"] == extras
            and summary["reversed"] == reversals
            and duplicate_hits == options["duplicates"]
        )

        self.stdout.write(self.style.MIGRATE_HEADING(f"Ensaio na distribuição #{distribution.pk}"))
        self.stdout.write(f"  leituras únicas:       {delivered}")
        self.stdout.write(f"  duplicidades barradas: {duplicate_hits}/{options['duplicates']}")
        self.stdout.write(f"  excedentes:            {extras}")
        self.stdout.write(f"  estornos:              {reversals}")
        self.stdout.write(f"  regular esperada:      {expected_regular}")
        self.stdout.write(f"  resumo:                {summary}")

        if options["cleanup"]:
            self._cleanup(distribution, group, students)
            self.stdout.write(self.style.WARNING("Dados do ensaio removidos (--cleanup)."))

        if not ok:
            raise CommandError("Incoerência nos totais do ensaio.")
        self.stdout.write(self.style.SUCCESS("Ensaio coerente: OK"))

    def _resolve_campus(self, options):
        if options["campus"]:
            campus = Campus.objects.filter(code=options["campus"]).first()
            if campus is None:
                raise CommandError(f"Campus não encontrado: {options['campus']}")
            return campus
        campus = resolve_campus(self._resolve_user())
        if campus is None:
            raise CommandError("Informe --campus (ambíguo ou inexistente).")
        return campus

    def _resolve_user(self):
        user = User.objects.filter(is_superuser=True).order_by("pk").first()
        if user is None:
            raise CommandError("Nenhum superusuário disponível.")
        return user

    def _ensure_students(self, campus, group, count):
        students = []
        for index in range(1, count + 1):
            student, _ = Student.objects.get_or_create(
                campus=campus,
                registration_number=f"DRILL-{index:04d}",
                defaults={"full_name": f"Estudante Ensaio {index:03d}", "class_group": group},
            )
            students.append(student)
        return students

    def _cleanup(self, distribution, group, students):
        with transaction.atomic():
            distribution.deliveries.all().delete()
            distribution.delete()
            Student.objects.filter(pk__in=[s.pk for s in students]).delete()
            group.delete()
