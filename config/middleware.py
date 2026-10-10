"""Middlewares do projeto."""

from django.shortcuts import redirect

# Rotas que não exigem campus (autenticação, PWA, APIs, a própria escolha).
EXEMPT_PREFIXES = (
    "/login/",
    "/logout/",
    "/admin/",
    "/static/",
    "/media/",
    "/campus/",
    "/aluno/",
    "/api/",
    "/healthz/",
    "/manifest.webmanifest",
    "/service-worker.js",
)


class ActiveCampusMiddleware:
    """Garante um campus ativo para a equipe.

    Quando o usuário **não** tem campus no cadastro (administrador global) e há
    mais de um campus ativo, o contexto fica ambíguo; manda para a página de
    escolha de campus. Usuários com campus vinculado nunca são afetados.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if (
            user is not None
            and user.is_authenticated
            and not getattr(user, "campus_id", None)
            and not request.path.startswith(EXEMPT_PREFIXES)
        ):
            from apps.campus.selectors import resolve_campus

            if resolve_campus(user, request) is None:
                return redirect(f"/campus/?next={request.get_full_path()}")
        return self.get_response(request)
