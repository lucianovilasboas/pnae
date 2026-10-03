# 01 — Arquitetura

Decisões de arquitetura do MVP. Referência de produto:
[`../plano_mvp_ifmg_alimenta.md`](../plano_mvp_ifmg_alimenta.md) §9. Padrão de
projeto espelhado de `ifeventos_app` / `dentista_app`.

## 1. Stack

| Camada | Escolha | Observação |
|---|---|---|
| Linguagem | Python 3.12 | alinhado aos projetos irmãos |
| Framework | Django 5.x | admin pronto, ORM, sessões, segurança |
| Banco | PostgreSQL 16 | permite a constraint única parcial transacional |
| UI | Django templates + HTMX + Tailwind CSS | fluxo de scanner sem SPA |
| QR | geração server-side; token opaco armazenado como hash | ver `02-modelo-dados.md` |
| Servidor | Gunicorn (prod) / runserver (dev) | atrás de proxy reverso |
| Empacotamento | Docker + Docker Compose | `docker-compose.dev.yml` e `docker-compose.yml` |
| Proxy / TLS | Traefik (padrão dos irmãos) | HTTPS obrigatório fora do local |

### O que foi descartado no MVP

- fila de sincronização offline e microsserviços;
- app nativo e front-end React/SPA separado;
- workflow de autorização sofisticado (bastam permissões por usuário).

## 2. Aplicações Django

Um projeto `config` com apps sob `apps/`:

```
config/                 # settings (base/dev/prod), urls, wsgi/asgi, celery? (não)
apps/accounts/          # User custom, papéis, permissões extras, login
apps/campus/            # Campus, ClassGroup
apps/students/          # Student, StudentAccount, ImportJob, importação, QR
apps/menus/             # Menu (com publicação para o aluno)
apps/portal/            # portal do aluno: login, cardápio e QR
apps/distributions/     # Distribution, Delivery, regras, endpoint /scan
apps/audit/             # AuditEvent
templates/              # base + telas (operação, pendentes, relatório)
static/                 # Tailwind, HTMX, JS do scanner
```

Regras de dependência:

- `distributions` depende de `campus`, `students`, `menus`, `accounts`;
- `audit` é uma folha (não importa os demais) e é acionado por todos;
- `accounts` não depende de domínio, exceto por `campus_id` nullable.

## 3. Layout de repositório (Fase 2 — implementado como scaffold)

```
pnae_app/
├── config/                 # projeto Django (settings/, urls, wsgi, asgi)
├── apps/                   # apps de domínio
├── templates/              # templates compartilhados
├── static/                 # fontes de front (Tailwind via CDN no MVP)
├── requirements.txt
├── manage.py
├── pytest.ini
├── Dockerfile
├── entrypoint.sh
├── docker-compose.dev.yml  # portas publicadas, DEBUG=True, runserver
├── docker-compose.yml      # prod, sem portas expostas, atrás do Traefik
└── .env.example
```

## 4. Ambientes

- **dev:** `docker-compose.dev.yml`, `DEBUG=True`, `runserver` com reload,
  porta **8601** publicada no host (DB em 5433). Contêiner `pnae_app_django`
  (não `app_django`, que já é usado pelo `ifeventos_app` na mesma máquina).
- **prod:** `docker-compose.yml`, `DEBUG=False`, Gunicorn, TLS no Traefik,
  sem portas de banco expostas.
- Banco em **volume Docker nomeado** (`pgdata`) em ambos — evita problemas de
  permissão de bind mount e simplifica o backup via `pg_dump`.
- Segredos via `.env` (nunca versionado; `.env.example` é o modelo).
- `DJANGO_SETTINGS_MODULE`: `config.settings.dev` (dev) / `config.settings.prod`
  (prod). `manage.py` assume `dev` por padrão.

## 5. Camadas e responsabilidades

| Camada | Responsabilidade |
|---|---|
| Views/HTMX | orquestrar requisição, montar contexto, devolver fragmento |
| Services (`apps/*/services.py`) | regras de negócio e transações atômicas |
| Models | persistência, invariantes simples, validações de campo |
| ORM/constraints | garantia final: unicidade parcial, FKs, `select_for_update` |
| Audit | gravar `AuditEvent` para toda operação relevante |

O endpoint de leitura (`POST /scan`) **nunca** contém regra de negócio na view:
a view chama o service, que abre a transação e usa a constraint do banco como
árbitro final da duplicidade.

## 6. Autenticação e perfis

- Sessão Django (cookie seguro) — decisão recomendada; JWT não é necessário
  para templates/HTMX. Endpoints JSON reutilizam a sessão.
- `User` custom com `campus_id` nullable (admin global) e papéis
  `ADMIN`, `OPERATOR`, `MANAGER` (somente leitura).
- Permissões extras por usuário: `can_authorize_extras`,
  `can_reverse_deliveries`.
- Toda query e mutação filtram por `campus_id` do usuário quando não for
  admin global.

## 7. Mapa de telas (§7 do plano) para views

| Tela | App | Tipo |
|---|---|---|
| Login | accounts | página |
| Painel inicial | distributions | página |
| Estudantes | students | página + HTMX |
| Importar estudantes | students | wizard (upload → prévia → confirmar) |
| QR Codes | students | geração em lote + folha de impressão |
| Cardápios | menus | CRUD |
| Distribuições | distributions | CRUD + ações abrir/encerrar |
| Operação de entrega | distributions | página HTMX com foco + scanner |
| Autorização de excedente | distributions | modal/página com reautenticação |
| Pendentes | distributions | página + filtro por turma |
| Relatório diário | distributions | página imprimível + export CSV/PDF |
| Auditoria | audit | página com filtros |

## 8. Comportamento da tela de operação

- campo de leitura inicia focado e **recupera o foco após cada resposta**;
- câmera via `getUserMedia` quando o navegador permitir;
- scanner USB funciona como teclado: token + `Enter`;
- feedback inequívoco: verde = entregue, vermelho = duplicidade, amarelo = QR
  inválido (visual + texto; som opcional);
- exibir apenas o necessário (nome, turma, matrícula são aceitáveis para
  reduzir erro);
- **registrar antes de exibir “entregue”** — nunca o contrário;
- Operação por scanner USB e câmera; **app instalável (PWA)**: `manifest` +
  ícones + service worker (cache só de estáticos; nenhuma operação offline).

## 9. Não-objetivos de arquitetura (MVP)

- offline/fila; multi-campus pleno; integração acadêmica; SPA; BI.
