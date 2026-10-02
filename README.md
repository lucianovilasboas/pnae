# IFMG Alimenta (PNAE)

Sistema web responsivo/PWA (instalável) para registrar e acompanhar a **distribuição de
alimentação escolar por QR Code** do PNAE no IFMG. O foco do MVP é uma sessão
de distribuição rápida e **auditável**: ler o QR do estudante, registrar a
entrega regular, bloquear duplicidade e permitir excedente somente com
autorização e motivo.

- **Plano de produto (MVP):** [`plano_mvp_ifmg_alimenta.md`](plano_mvp_ifmg_alimenta.md)
- **Plano de implementação (engenharia):** [`docs/`](docs/)

> **Status:** Marcos 0–3 completos e Marco 4 com as ferramentas de piloto
> prontas: projeto Django (apps, modelos, migrations com índice único parcial),
> admin auditado, Docker Compose, importação de estudantes (CSV/XLSX, com
> criação de turmas), QR Codes, operação de entrega com leitura atômica
> (`/scan`), relatório diário, estorno/auditoria, **ensaio de volume**
> (`pilot_drill`) e **backup/restauração** documentados. Dados reais de Ponte
> Nova carregados (309 alunos). Falta o que depende de pessoas/instituição:
> treinamento e sessão piloto — ver [`docs/04-marcos.md`](docs/04-marcos.md).

## Operação

Runbook em [`docs/08-operacao.md`](docs/08-operacao.md): backup
(`./scripts/backup_db.sh`), restauração (`./scripts/restore_db.sh`), ensaio
(`python manage.py pilot_drill --campus PN --students 60`) e deploy. Leitura na
operação por **scanner USB** (teclado) ou **câmera do celular** (QR Code e
códigos de barras 1D via ZXing; a câmera requer HTTPS).

## Telas principais

| Tela | Rota |
|---|---|
| Painel | `/` |
| Distribuições (criar/abrir/encerrar) | `/distribuicoes/` |
| Operação de entrega | `/distribuicoes/<id>/operar/` |
| Entregas (estorno) | `/distribuicoes/<id>/entregas/` |
| Pendentes | `/distribuicoes/<id>/pendentes/` |
| Relatório diário | `/distribuicoes/<id>/relatorio/` |
| Cardápios | `/cardapios/` |
| Importar estudantes | `/estudantes/importar/` |
| QR Codes | `/estudantes/qr/` |
| Auditoria | `/auditoria/` |

Roteiro do operador (1 página) em
[`docs/09-treinamento-operador.md`](docs/09-treinamento-operador.md). Deploy em
produção (OVM-1) em [`docs/10-deploy-ovm1.md`](docs/10-deploy-ovm1.md).

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
| PWA | app instalável: manifest + ícones + service worker (cache só de estáticos) |
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
