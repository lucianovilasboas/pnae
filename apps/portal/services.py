"""Regras de acesso do portal do aluno.

O aluno entra com e-mail + senha. A senha é definida no primeiro acesso e na
recuperação, sempre com prova de identidade por **matrícula + CPF** (sem envio
de e-mail). A sessão do aluno é isolada do `accounts.User` da equipe.
"""

import re

from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.students.models import Student, StudentAccount


class PortalAuthError(ValueError):
    pass


def _only_digits(value):
    return re.sub(r"\D", "", value or "")


def _find_student(registration_number):
    rn = (registration_number or "").strip()
    if not rn:
        raise PortalAuthError("Informe a matrícula.")
    matches = list(
        Student.objects.filter(registration_number=rn, active=True).select_related("campus")[:2]
    )
    if not matches:
        raise PortalAuthError("Matrícula não encontrada.")
    if len(matches) > 1:
        raise PortalAuthError("Matrícula ambígua; fale com a secretaria.")
    return matches[0]


def _verify_cpf(student, cpf):
    expected = _only_digits(student.cpf)
    if not expected:
        raise PortalAuthError("Cadastro sem CPF; procure a secretaria.")
    if _only_digits(cpf) != expected:
        raise PortalAuthError("CPF não confere.")


def _validate_password(password, password2=None):
    if password2 is not None and password != password2:
        raise PortalAuthError("As senhas não conferem.")
    try:
        password_validation.validate_password(password)
    except ValidationError as exc:
        raise PortalAuthError(" ".join(exc.messages)) from exc


def first_access(*, registration_number, cpf, password, password2=None):
    """Cria a conta do aluno após provar identidade (matrícula + CPF)."""
    student = _find_student(registration_number)
    _verify_cpf(student, cpf)
    _validate_password(password, password2)
    if not student.email:
        raise PortalAuthError("Cadastro sem e-mail; procure a secretaria.")
    if StudentAccount.objects.filter(student=student).exists():
        raise PortalAuthError("Já existe uma conta; faça login ou recupere a senha.")
    if StudentAccount.objects.filter(email__iexact=student.email).exists():
        raise PortalAuthError("Este e-mail já está em uso; procure a secretaria.")

    account = StudentAccount(student=student, email=student.email)
    account.set_password(password)
    account.save()
    return account


def authenticate(*, email, password):
    account = (
        StudentAccount.objects.select_related("student")
        .filter(email__iexact=(email or "").strip())
        .first()
    )
    if account is None or not account.check_password(password or ""):
        return None
    if not account.is_active or not account.student.active:
        return None
    account.last_login_at = timezone.now()
    account.save(update_fields=["last_login_at", "updated_at"])
    return account


def recover(*, registration_number, cpf, password, password2=None):
    """Redefine a senha provando identidade (matrícula + CPF)."""
    student = _find_student(registration_number)
    _verify_cpf(student, cpf)
    _validate_password(password, password2)
    account = StudentAccount.objects.filter(student=student).first()
    if account is None:
        raise PortalAuthError("Ainda não há conta; use o primeiro acesso.")
    account.set_password(password)
    account.save(update_fields=["password", "updated_at"])
    return account
