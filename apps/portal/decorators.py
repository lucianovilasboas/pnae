"""Sessão e autorização do portal do aluno.

Usa uma chave de sessão própria (`portal_account_id`), isolada do
`accounts.User` da equipe. Um aluno logado **não** autentica nas telas da
equipe (que dependem de `request.user`), e vice-versa.
"""

from functools import wraps

from django.shortcuts import redirect

from apps.students.models import StudentAccount

SESSION_KEY = "portal_account_id"


def get_current_account(request):
    account_id = request.session.get(SESSION_KEY)
    if not account_id:
        return None
    return (
        StudentAccount.objects.select_related("student", "student__campus")
        .filter(pk=account_id, is_active=True, student__active=True)
        .first()
    )


def login_account(request, account):
    request.session.cycle_key()
    request.session[SESSION_KEY] = account.pk


def logout_account(request):
    request.session.pop(SESSION_KEY, None)


def student_login_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        account = get_current_account(request)
        if account is None:
            return redirect("portal:login")
        request.portal_account = account
        return view(request, *args, **kwargs)

    return wrapper
