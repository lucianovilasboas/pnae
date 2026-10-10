"""Seletores de campus (leitura/escopo)."""

from .models import Campus


def resolve_campus(user, request=None):
    """Campus efetivo para a operação (contexto da aplicação).

    Ordem de precedência:

    1. **campus vinculado ao usuário** (cadastro) — caso normal: operador/gestor
       já opera no seu campus sem informar nada;
    2. **campus escolhido na sessão** — só quando o usuário *não* tem campus
       vinculado (administrador global), permitindo atuar em outro campus;
    3. `campus` informado na requisição (telas em lote), se houver;
    4. único campus ativo (cenário de campus único do MVP);
    5. `None` (ambíguo → a página de escolha de campus resolve).
    """
    if getattr(user, "campus_id", None):
        return user.campus

    session = getattr(request, "session", None) if request is not None else None
    if session is not None:
        campus_id = session.get("campus_id")
        if campus_id:
            campus = Campus.objects.filter(pk=campus_id, active=True).first()
            if campus is not None:
                return campus

    if request is not None:
        campus_id = request.POST.get("campus") or request.GET.get("campus")
        if campus_id:
            campus = Campus.objects.filter(pk=campus_id, active=True).first()
            if campus is not None:
                return campus

    active = Campus.objects.filter(active=True)
    if active.count() == 1:
        return active.first()
    return None
