# 10 — Deploy em produção (OVM-1)

Publicar o IFMG Alimenta em `https://pnae.lucianovilasboas.com.br` na máquina
**OVM-1**, atrás do Traefik. Há **dois caminhos**: script (rápido) e manual.

Pré-requisitos na OVM-1: Docker + Docker Compose, Traefik rodando com a rede
externa **`proxy`** e o resolver `letsencrypt`, e as portas 80/443 no Traefik.

---

## Caminho A — Script (recomendado)

O script `scripts/deploy.sh` faz tudo: valida o `.env`, sobe a stack
(migrate + collectstatic rodam no entrypoint) e espera o site responder.
Ele **não pergunta nada** — você preenche o `.env` antes.

### A1. Clonar

`git clone https://github.com/lucianovilasboas/pnae.git`

`cd pnae`

### A2. Criar o `.env`

`cp .env.example .env`

Gere os segredos:

`python3 -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(50))"`

`python3 -c "import secrets; print('QR_PEPPER=' + secrets.token_urlsafe(32))"`

### A3. Editar o `.env`

Deixe exatamente estes valores (troque só os segredos e a senha):

`DEBUG=False`

`ALLOWED_HOSTS=pnae.lucianovilasboas.com.br`

`CSRF_TRUSTED_ORIGINS=https://pnae.lucianovilasboas.com.br`

`USE_HTTPS_PROXY=True`

`SECRET_KEY=<o valor gerado em A2>`

`QR_PEPPER=<o valor gerado em A2>`

`DATABASE_URL=postgres://django_user:SENHA@db:5432/django_db`

`POSTGRES_DB=django_db`

`POSTGRES_USER=django_user`

`POSTGRES_PASSWORD=SENHA`

### A4. Rodar o deploy

`./scripts/deploy.sh`

### A5. Criar o administrador

`docker exec -it pnae_app python manage.py createsuperuser`

### A6. Importar os estudantes (opcional agora)

`./scripts/importar_alunos.sh --user luciano.espiridiao@ifmg.edu.br`

Confira a prévia; para **gravar**, repita com `--apply`:

`./scripts/importar_alunos.sh --user luciano.espiridiao@ifmg.edu.br --apply`

---

## Caminho B — Manual

Mesmos passos, sem script. Um comando por linha.

### B1. Clonar

`git clone https://github.com/lucianovilasboas/pnae.git`

`cd pnae`

### B2. Criar e preencher o `.env` (igual a A2/A3)

`cp .env.example .env`

`python3 -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(50))"`

`python3 -c "import secrets; print('QR_PEPPER=' + secrets.token_urlsafe(32))"`

Edite o `.env` com `DEBUG=False`, `USE_HTTPS_PROXY=True`, o domínio em
`ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS`, a `DATABASE_URL`/`POSTGRES_PASSWORD`
e os segredos acima.

### B3. Subir

`docker compose up -d --build`

### B4. Superusuário

`docker exec -it pnae_app python manage.py createsuperuser`

### B5. Verificar

`curl https://pnae.lucianovilasboas.com.br/healthz/`

Deve responder `{"status": "ok", "database": true}`.

### B6. Importar estudantes

Prévia (não grava):

`docker exec pnae_app python manage.py import_roster /pnae_app/alunos-ifmg-pn-matricula-mapeada.xlsx --campus PN --campus-name "IFMG — Campus Ponte Nova" --academic-year 2026 --user luciano.espiridiao@ifmg.edu.br --dry-run`

Aplicar:

`docker exec pnae_app python manage.py import_roster /pnae_app/alunos-ifmg-pn-matricula-mapeada.xlsx --campus PN --campus-name "IFMG — Campus Ponte Nova" --academic-year 2026 --user luciano.espiridiao@ifmg.edu.br`

---

## Arquivo da planilha

Use `alunos-ifmg-pn-matricula-mapeada.xlsx` (já com a coluna **Turma**
mapeada para `ADM 1`, `Info 1A`, …). Ele **não** vai no git (dados reais).
Copie-o para a raiz do projeto na OVM-1 (é o caminho usado pelos comandos e
pelo script).

## Rotina e backup

Backup do banco: `./scripts/backup_db.sh` (agende no cron, ex.: diário às 2h).

Testar restauração: `./scripts/restore_db.sh backups/pnae-AAAAMMDD-HHMMSS.sql.gz`

Ensaio de leitura: `docker exec pnae_app python manage.py pilot_drill --campus PN --students 60 --cleanup`

## Atualizar depois (novo deploy)

`git pull`

`docker compose up -d --build`

## PWA / instalação

O app é instalável (manifest + service worker). No navegador aparece a opção
**Instalar**; no iPhone use **Compartilhar → Adicionar à Tela de Início**.
`/manifest.webmanifest` e `/service-worker.js` respondem 200; a câmera exige
**HTTPS** (atendido pelo domínio).
