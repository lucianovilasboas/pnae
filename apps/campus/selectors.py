"""Seletores de campus (leitura/escopo)."""

from .models import Campus


def resolve_campus(user, request=None):
    """Campus efetivo para a operação.

    - usuário com campus definido → o próprio;
    - admin global (sem campus) → `campus` informado na requisição ou, no
      cenário single-campus do MVP, o único campus ativo existente;
    - caso contrário → None (ambíguo, quem chama deve recusar).
    """
    if getattr(user, "campus_id", None):
        return user.campus

    if request is not None:
        campus_id = request.POST.get("campus") or request.GET.get("campus")
        if campus_id:
            return Campus.objects.filter(pk=campus_id, active=True).first()

    active = Campus.objects.filter(active=True)
    if active.count() == 1:
        return active.first()
    return None
