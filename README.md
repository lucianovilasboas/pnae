# IFMG Alimenta (PNAE)

Sistema web responsivo/PWA para registrar e acompanhar a **distribuição de
alimentação escolar por QR Code** do PNAE no IFMG. O foco do MVP é uma sessão
de distribuição rápida e **auditável**: ler o QR do estudante, registrar a
entrega regular, bloquear duplicidade e permitir excedente somente com
autorização e motivo.

- **Plano de produto (MVP):** [`plano_mvp_ifmg_alimenta.md`](plano_mvp_ifmg_alimenta.md)
- **Plano de implementação (engenharia):** [`docs/`](docs/)

> **Status:** Marcos 1, 2 e 3 entregues. Projeto Django completo (apps, modelos,
> migrations com índice único parcial), admin auditado, Docker Compose,
> importação de estudantes (CSV/XLSX), QR Codes, **operação de entrega** com
> leitura atômica (`/scan`) e bloqueio de duplicidade, **relatório diário**
> (página imprimível + CSV), estorno auditável e tela de auditoria. Próximo:
> Marco 4 (piloto e estabilização) — ver
> [`docs/04-marcos.md`](docs/04-marcos.md).

## Telas principais

| Tela | Rota |
|---|---|
| Painel | `/` |
| Distribuições (criar/abrir/encerrar) | `/distribuicoes/` |
| Operação de entrega | `/distribuicoes/<id>/operar/` |
| Entregas (estorno) | `/distribuicoes/<id>/entregas/` |
| Pendentes | `/distribuicoes/<id>/pendentes/` |
| Relatório diário | `/distribuicoes/<id>/relatorio/` |
| Importar estudantes | `/estudantes/importar/` |
| QR Codes | `/estudantes/qr/` |
| Auditoria | `/auditoria/` |

## Como rodar (desenvolvimento)

```bash
cp .env.example .env                 # e ajuste se necessário
docker compose -f docker-compose.dev.yml up -d --build
```

Acesse http://127.0.0.1:8601/ (admin em `/admin/`). O banco de dados é um
volume Docker (`pgdata`). Pare com:

```bash
docker compose -f docker-compose.dev.yml down       # mantém os dados
docker compose -f docker-compose.dev.yml down -v    # apaga o volume
```

Crie o primeiro usuário administrador:

```bash
docker exec -it pnae_app_django python manage.py createsuperuser
```

Rode os testes:

```bash
docker exec pnae_app_django bash -lc 'cd /pnae_app && python -m pytest'
```

---

## Stack prevista

| Camada | Escolha |
|---|---|
| Backend e páginas | Django 5 + Python 3.12 |
| Banco | PostgreSQL 16 |
| UI | Django templates + HTMX + Tailwind CSS |
| QR Code | biblioteca Python; token opaco armazenado como hash |
| PWA | manifesto + ícones + HTTPS; cache só de estáticos no MVP |
| Empacotamento | Docker / Docker Compose (dev e prod) |

Justificativa e alternativas descartadas em
[`docs/01-arquitetura.md`](docs/01-arquitetura.md).

## Estrutura do repositório

```
.
├── plano_mvp_ifmg_alimenta.md   # plano de produto (fonte de verdade das regras)
├── docs/                        # plano de implementação de engenharia
│   ├── 01-arquitetura.md
│   ├── 02-modelo-dados.md
│   ├── 03-api.md
│   ├── 04-marcos.md
│   ├── 05-testes.md
│   ├── 06-decisoes-abertas.md
│   └── 07-seguranca-lgpd.md
├── AGENTS.md                    # convenções de trabalho do repositório
└── README.md
```

## Documentação

| Documento | Assunto |
|---|---|
| [01-arquitetura](docs/01-arquitetura.md) | stack, apps Django, layout, ambientes, telas |
| [02-modelo-dados](docs/02-modelo-dados.md) | models, migrations, índices e constraints |
| [03-api](docs/03-api.md) | rotas, contrato do `/scan`, atomicidade |
| [04-marcos](docs/04-marcos.md) | Marcos 0–4 em tarefas de engenharia verificáveis |
| [05-testes](docs/05-testes.md) | estratégia de testes e critérios de aceite |
| [06-decisoes-abertas](docs/06-decisoes-abertas.md) | perguntas institucionais e ADRs pendentes |
| [07-seguranca-lgpd](docs/07-seguranca-lgpd.md) | controles de segurança, LGPD e operação |

## Escopo do MVP

**Incluído:** administração de campus/turmas/estudantes, importação CSV/XLSX,
geração de QR, cardápio simples, abertura/operação/encerramento de
distribuições, leitura por câmera e scanner USB, entrega regular, bloqueio de
duplicidade, excedente autorizado, painel de totais/pendentes, relatório
diário, autenticação por perfis, auditoria e estorno.

**Fora do MVP:** estoque/compras/custos, integração acadêmica, restrições
alimentares, portal do estudante, login Google, offline/sincronização,
multi-campus operacional e BI.

Detalhes completos no [plano do MVP](plano_mvp_ifmg_alimenta.md).
