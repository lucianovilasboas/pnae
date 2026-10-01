# 03 — API

Contratos das rotas do §8 do [plano do MVP](../plano_mvp_ifmg_alimenta.md).
A versão inicial usa páginas Django/HTMX e expõe JSON apenas onde a leitura
assíncrona exigir (`/scan`, `summary`, `pending`, importação).

## 1. Convenções

- Base: `/api/`.
- Autenticação: **sessão Django** (cookie seguro); CSRF obrigatório em
  `POST`/`PATCH`/`DELETE`.
- Erros: JSON `{"detail": "...", "code": "..."}` com status HTTP coerente.
- Todas as rotas filtram por `campus_id` do usuário (admin global é exceção).
- Datas/horas em ISO-8601 com offset; armazenamento em UTC.
- Nenhuma resposta devolve token QR nem dados sensíveis além do necessário.

## 2. Rotas

| Método e rota | Finalidade | Notas |
|---|---|---|
| `POST /api/auth/login` | autenticar equipe | cria sessão |
| `POST /api/auth/logout` | encerrar sessão | — |
| `GET /api/distributions/current` | distribuição aberta do campus | 404 se não houver |
| `POST /api/distributions` | criar rascunho | valida data/refeição |
| `POST /api/distributions/{id}/open` | abrir distribuição | `DRAFT → OPEN` |
| `POST /api/distributions/{id}/close` | encerrar distribuição | `OPEN → CLOSED` |
| `POST /api/distributions/{id}/scan` | ler token e tentar entrega regular | **atômico** |
| `POST /api/distributions/{id}/extras` | registrar excedente autorizado | exige autorizador |
| `POST /api/deliveries/{id}/reverse` | estornar entrega | exige motivo |
| `GET /api/distributions/{id}/summary` | totais ao vivo | painel |
| `GET /api/distributions/{id}/pending` | pendentes | filtro `class_group` |
| `GET /api/distributions/{id}/report` | relatório/exportação | `format=csv\|pdf\|html` |
| `POST /api/students/imports` | enviar arquivo | CSV/XLSX, gera prévia |
| `POST /api/students/imports/{id}/apply` | confirmar importação | aplica após prévia |
| `GET /api/students/qr-export` | exportar QR Codes | filtro por turma |

## 3. `POST /api/distributions/{id}/scan`

Payload:
```json
{ "token": "<token opaco lido do QR>", "device": "usb-scanner-1" }
```

Resposta (sempre 200 quando a requisição é válida; o resultado vai no corpo):
```json
{
  "result": "DELIVERED | ALREADY_DELIVERED | INVALID_TOKEN | INELIGIBLE | DISTRIBUTION_CLOSED",
  "student": {"id": 1, "name": "Nome", "registrationNumber": "2024001", "className": "1º Ano A"},
  "delivery": {"id": 10, "type": "REGULAR", "deliveredAt": "2026-10-01T11:32:00-03:00"},
  "previousDelivery": null,
  "message": "Entrega registrada"
}
```

Regras por `result`:

| `result` | Status | Efeito |
|---|---|---|
| `DELIVERED` | 200 | cria `Delivery REGULAR`; `delivery` preenchido |
| `ALREADY_DELIVERED` | 200 | **não** cria; `previousDelivery` com tipo/hora |
| `INVALID_TOKEN` | 200 | não cria; `student`/`delivery` nulos |
| `INELIGIBLE` | 200 | estudante inativo ou de outro campus |
| `DISTRIBUTION_CLOSED` | 200 | distribuição não está `ABERTA` |

- Para `ALREADY_DELIVERED`, `previousDelivery` traz ao menos
  `{type, deliveredAt}` (e `id`).
- **Nunca** retornar o token; nunca dados além de nome, matrícula e turma.
- Erros de requisição (payload inválido, sem permissão, distribuição
  inexistente) usam 400/403/404 — distintos dos resultados de negócio acima.

## 4. Atomicidade do `/scan`

Sequência no service (dentro de `transaction.atomic()`):

1. validar payload e permissão;
2. carregar `Distribution` do campus do usuário; se não `OPEN` →
   `DISTRIBUTION_CLOSED`;
3. `hash = HMAC-SHA256(pepper, token)`; buscar `Student` por `qr_token_hash`;
   não achou → `INVALID_TOKEN`;
4. se `Student.active` falso ou campus diferente → `INELIGIBLE`;
5. tentar inserir `Delivery REGULAR VALIDA`;
6. sucesso → `DELIVERED`;
7. `IntegrityError` na constraint única parcial → reconsultar a entrega
   existente e responder `ALREADY_DELIVERED` com `previousDelivery`.

> A etapa 5 é um único `INSERT`. É a constraint do banco que decide o empate
> entre duas leituras concorrentes; a aplicação apenas interpreta o
> `IntegrityError`. Não usar “ler-depois-escrever” sem constraint.

Alternativa equivalente: `INSERT ... ON CONFLICT DO NOTHING` + verificação de
linhas afetadas (`RETURNING`).

## 5. `POST /api/deliveries/{id}/reverse`

```json
{ "reason": "Leitura em estudante errado" }
```
- Exige `can_reverse_deliveries` (ou `ADMIN`).
- Seta `status=ESTORNADA` + `reversed_*`; grava `AuditEvent`. Original intacto.
- 409 se a entrega não estiver `VALIDA`.

## 6. `POST /api/distributions/{id}/extras`

```json
{ "token": "<opaco>",   "reason": "Segunda refeição autorizada pela coordenação" }
```
- Exige `can_authorize_extras` (ou `ADMIN`); exige `reason` não vazio.
- Cria `Delivery EXCEDENTE VALIDA` com `authorized_by` = usuário atual e
  `recorded_by` = operador solicitante (ver pergunta institucional 4).
- Não substitui nem altera a entrega `REGULAR`.

## 7. `GET /api/distributions/{id}/summary`

```json
{
  "eligible": 320,
  "regularValid": 298,
  "extrasValid": 5,
  "pending": 22,
  "reversed": 2,
  "attendanceRate": 0.931
}
```
- `pending = eligible - regularValid` (excedente não reduz pendência).
- Considera apenas entregas `VALIDA` para os indicadores operacionais.

## 8. Importação de estudantes

- `POST /api/students/imports` (multipart, campo `file`) → cria `ImportJob`
  em `PREVIEW` com prévia e relatório de rejeitadas; **não** altera a base.
- `POST /api/students/imports/{id}/apply` → aplica a prévia de forma
  transacional; atualiza contadores; gera `AuditEvent`.
- `GET /api/students/imports/{id}/errors` → baixa relatório de linhas
  rejeitadas (CSV).

## 9. Relatório diário

`GET /api/distributions/{id}/report?format=csv|pdf|html`:

- `html` = página imprimível (layout institucional a definir);
- `csv` e `pdf` respeitam permissões e retornam apenas colunas necessárias
  (RN-12 / LGPD);
- conteúdo: totais (aptos, regulares válidas, excedentes, pendentes, estornos),
  detalhamento por turma, lista de pendentes e trilha de eventos do dia.
