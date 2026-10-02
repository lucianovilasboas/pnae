# 10 — Deploy em produção (OVM-1)

Passo a passo para publicar o IFMG Alimenta em
`https://pnae.lucianovilasboas.com.br` na máquina **OVM-1**, atrás do Traefik.

## Pré-requisitos (na OVM-1)

- Docker e Docker Compose instalados.
- Traefik já rodando, com a **rede externa `proxy`** e o resolver
  `letsencrypt` (mesma configuração dos projetos irmãos `ifeventos_app` /
  `dentista_app`).
- Porta 443/80 livres (o Traefik expõe; o app não publica porta no host).

## 1. Clonar o repositório

```bash
git clone https://github.com/lucianovilasboas/pnae.git
cd pnae
git checkout main          # já contém tudo (tags até v0.12.0)
```

## 2. Criar o `.env` de produção

```bash
cp .env.example .env
# gere segredos fortes:
python3 -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(50))"
python3 -c "import secrets; print('QR_PEPPER=' + secrets.token_urlsafe(32))"
```

Preencha o `.env`:

```
SECRET_KEY=<cole o gerado>
DEBUG=False
ALLOWED_HOSTS=pnae.lucianovilasboas.com.br
TIME_ZONE=America/Sao_Paulo
DATABASE_URL=postgres://django_user:<SENHA_FORTE>@db:5432/django_db
POSTGRES_DB=django_db
POSTGRES_USER=django_user
POSTGRES_PASSWORD=<SENHA_FORTE>
QR_PEPPER=<cole o gerado>
USE_HTTPS_PROXY=True
CSRF_TRUSTED_ORIGINS=https://pnae.lucianovilasboas.com.br
```

> O `SECRET_KEY`/`QR_PEPPER` **não podem** ser os de exemplo. `POSTGRES_PASSWORD`
> deve ser forte.

## 3. Subir a aplicação

```bash
docker compose up -d --build
```

O `entrypoint.sh` do contêiner roda `migrate` e `collectstatic`
automaticamente; o Traefik emite o certificado Let's Encrypt para o domínio
(label já configurado em `docker-compose.yml`).

## 4. Criar o superusuário

```bash
docker exec -it pnae_app python manage.py createsuperuser
```

## 5. Conferir

```bash
curl https://pnae.lucianovilasboas.com.br/healthz/
# -> {"status": "ok", "database": true}
```

- App: https://pnae.lucianovilasboas.com.br/
- Admin: https://pnae.lucianovilasboas.com.br/admin/
- O ícone “Instalar app” (PWA) aparece no navegador; `/manifest.webmanifest`
  e `/service-worker.js` respondem 200.

## 6. Importar os estudantes

Use o arquivo **`alunos-ifmg-pn-matricula-mapeada.xlsx`** (já com a coluna
`Turma` mapeada para `ADM 1`, `Info 1A`, etc.):

```bash
# validar sem gravar
docker exec pnae_app python manage.py import_roster \
  /pnae_app/alunos-ifmg-pn-matricula-mapeada.xlsx \
  --campus PN --campus-name "IFMG — Campus Ponte Nova" --academic-year 2026 \
  --user <seu-email> --dry-run

# aplicar
docker exec pnae_app python manage.py import_roster \
  /pnae_app/alunos-ifmg-pn-matricula-mapeada.xlsx \
  --campus PN --campus-name "IFMG — Campus Ponte Nova" --academic-year 2026 \
  --user <seu-email>
```

> Copie o `.xlsx` para dentro do contêiner ou coloque-o na raiz do projeto
> (ele é ignorado pelo git). Alternativa: importar pela tela
> **Estudantes → Importar**.

## 7. Backup e rotina

```bash
./scripts/backup_db.sh            # backup diário (agende no cron)
./scripts/restore_db.sh backups/pnae-AAAAMMDD-HHMMSS.sql.gz   # teste de restauração
```

## 8. Atualizar a aplicação (novo deploy)

```bash
git pull
docker compose up -d --build
```
