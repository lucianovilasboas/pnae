"""Carga de estudantes a partir de CSV/XLSX (prévia + aplicação).

Exemplo:
    python manage.py import_roster /pnae_app/alunos.xlsx \
        --campus PN --campus-name "IFMG — Campus Ponte Nova" --academic-year 2026

Use `--dry-run` para apenas validar, sem gravar nada.
"""

import os

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User
from apps.campus.models import Campus

from ...importers import RosterFormatError, missing_group_names, parse_roster
from ...services import apply_import, create_import_preview


class Command(BaseCommand):
    help = "Importa estudantes de uma planilha CSV/XLSX para um campus."

    def add_arguments(self, parser):
        parser.add_argument("path", help="caminho do arquivo CSV/XLSX")
        parser.add_argument("--campus", required=True, help="código do campus")
        parser.add_argument("--campus-name", default="", help="nome do campus (cria se faltar)")
        parser.add_argument("--academic-year", type=int, default=None, help="ano letivo das turmas")
        parser.add_argument("--user", default="", help="e-mail do autor da importação")
        parser.add_argument("--dry-run", action="store_true", help="apenas valida, não grava")

    def handle(self, *args, **options):
        path = options["path"]
        if not os.path.exists(path):
            raise CommandError(f"Arquivo não encontrado: {path}")

        campus = self._resolve_campus(options, dry_run=options["dry_run"])
        author = self._resolve_user(options)
        filename = os.path.basename(path)
        academic_year = options["academic_year"]

        if options["dry_run"]:
            with open(path, "rb") as handle:
                valid, errors, total = parse_roster(handle, filename, campus)
            new_groups = missing_group_names(campus, valid)
            self._report(filename, total, len(valid), errors, new_groups, dry_run=True)
            return

        with open(path, "rb") as handle:
            uploaded = File(handle, name=filename)
            job, valid, errors = create_import_preview(
                campus=campus, user=author, uploaded_file=uploaded, academic_year=academic_year
            )
        new_groups = missing_group_names(campus, valid)
        self._report(filename, job.total_rows, len(valid), errors, new_groups, dry_run=False)

        job = apply_import(job=job, user=author)
        self.stdout.write(
            self.style.SUCCESS(
                f"Importação #{job.pk} aplicada: {job.imported_rows} importados, "
                f"{job.rejected_rows} rejeitados."
            )
        )

    def _resolve_campus(self, options, dry_run=False):
        code = options["campus"]
        campus = Campus.objects.filter(code=code).first()
        if campus is None:
            if not options["campus_name"]:
                raise CommandError(
                    f"Campus '{code}' não existe. Informe --campus-name para criá-lo."
                )
            if dry_run:
                # Em dry-run não grava: usa um campus transiente só para validar.
                self.stdout.write(
                    self.style.WARNING(
                        f"[dry-run] campus '{code}' seria criado como '{options['campus_name']}'"
                    )
                )
                return Campus(code=code, name=options["campus_name"])
            campus = Campus.objects.create(code=code, name=options["campus_name"])
            self.stdout.write(self.style.WARNING(f"Campus criado: {campus.code} — {campus.name}"))
        return campus

    def _resolve_user(self, options):
        email = options["user"]
        if email:
            user = User.objects.filter(email=email).first()
            if user is None:
                raise CommandError(f"Usuário não encontrado: {email}")
            return user
        user = User.objects.filter(is_superuser=True).order_by("pk").first()
        if user is None:
            raise CommandError("Nenhum superusuário disponível; informe --user.")
        return user

    def _report(self, filename, total, valid_count, errors, new_groups, dry_run):
        mode = "DRY-RUN" if dry_run else "PRÉVIA"
        self.stdout.write(f"[{mode}] {filename}")
        self.stdout.write(f"  linhas: {total} | válidas: {valid_count} | rejeitadas: {len(errors)}")
        if new_groups:
            self.stdout.write(f"  turmas a criar ({len(new_groups)}): {', '.join(new_groups)}")
        for error in errors[:20]:
            self.stdout.write(f"  linha {error.line}: {error.registration_number} — {error.reason}")
        if len(errors) > 20:
            self.stdout.write(f"  ... e mais {len(errors) - 20} erro(s).")
