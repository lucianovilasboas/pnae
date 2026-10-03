# AGENTS.md — IFMG Alimenta (PNAE)

Convenções de trabalho deste repositório. Vale para qualquer agente (humano ou
IA) que altere o projeto. Espelha o padrão dos projetos irmãos
(`ifeventos_app`, `dentista_app`).

## Idioma

- Código, nomes de arquivos e commits em **inglês**; documentação e UI em
  **português**.
- Responder ao usuário no idioma em que ele escreve.

## Fluxo de trabalho de implementação (obrigatório)

Sempre que o usuário pedir uma implementação neste repositório:

1. **Criar uma branch nova** a partir da `main` antes de alterar qualquer
   arquivo (padrão: `feat/<tema>` ou `fix/<tema>`).
2. **Implementar** na branch.
3. **Testar** (ver seção Testes).
4. **Parar e aguardar autorização.** O usuário autoriza o merge e o push; só
   então faça o merge/push.

Nunca implemente direto na `main`. Nunca commite, faça merge ou push sem
autorização explícita.

> Enquanto o repositório estiver em fase de documentação (sem código), os
> documentos podem ir direto para a `main`, desde que autorizados.

## Padrão de commit

Mensagens curtas no imperativo, com prefixo de tipo (Conventional Commits):

```
feat: adiciona endpoint de leitura de QR
fix: corrige bloqueio de duplicidade concorrente
docs: detalha modelo de dados
chore: ajusta .gitignore
test: cobre estorno auditável
```

Um commit = uma mudança coerente. Não misturar assuntos.

## Testes

> A definir na Fase 2, quando o scaffold Django existir. Alvo previsto:

```bash
docker exec pnae_app_django bash -lc 'cd /pnae_app && python manage.py test -v 1'
```

Alternativa com pytest (recomendada no dia a dia):

```bash
docker exec pnae_app_django bash -lc 'cd /pnae_app && python -m pytest'
```

Antes de declarar uma tarefa concluída, rodar os testes afetados. Quando não
houver comando definido, perguntar ao usuário e registrar aqui.

## Regras de negócio inegociáveis

Vêm do plano do MVP e **não podem** ser afrouxadas na implementação:

- entrega regular única por `(distribution_id, student_id)`, garantida por
  **índice único parcial no PostgreSQL** — não só na aplicação;
- apenas distribuição `ABERTA` aceita entregas;
- excedente exige justificativa, operador solicitante e autorizador;
- estorno não apaga o registro original; correções são sempre por status +
  auditoria;
- QR codifica a matrícula do estudante (identificador único por campus); não
  expõe nome nem CPF;
- toda operação relevante gera `AuditEvent`.

## Dados e LGPD

- Nunca versionar bases reais de estudantes, `.env` ou segredos.
- Usar apenas dados **anonimizados** em testes e exemplos.
- Não registrar dados pessoais (nem senhas) em logs.

## Escopo

Antes de adicionar funcionalidade, conferir se está no **escopo do MVP**
(`README.md` / plano). Itens fora do MVP não entram sem decisão explícita.
