from django.db import connection
from django.http import JsonResponse


def healthcheck(request):
    """Sonda simples de saúde: processo vivo e banco acessível."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        database_ok = True
    except Exception:  # pragma: no cover - depende do ambiente
        database_ok = False

    return JsonResponse(
        {"status": "ok" if database_ok else "error", "database": database_ok},
        status=200 if database_ok else 503,
    )
