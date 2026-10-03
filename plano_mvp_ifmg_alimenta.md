# IFMG Alimenta — Plano do MVP

**Versão:** 0.1 (proposta)  
**Produto:** sistema web responsivo/PWA para registrar e acompanhar a distribuição de alimentação escolar por QR Code.  
**Escopo inicial:** um campus, com desenho preparado para expansão futura.

---

## 1. Resultado a alcançar

O MVP deve permitir que a equipe do PNAE realize uma sessão de distribuição com rapidez e rastreabilidade:

1. abre uma sessão associada a data, faixa de horário e cardápio;
2. lê o QR Code do estudante;
3. registra automaticamente a entrega regular;
4. bloqueia nova entrega regular na mesma sessão;
5. permite segunda entrega somente com autorização e motivo;
6. mostra totais de entregues e pendentes;
7. emite relatório diário auditável.

### Métricas de aceite

| Métrica | Meta do MVP |
|---|---:|
| Tempo de resposta após leitura válida | até 1 segundo em rede normal |
| Entrega regular duplicada | 0, bloqueada por regra de banco e aplicação |
| Auditoria de operações | 100% das entregas, autorizações, estornos e mudanças de status |
| Identificação no QR | matrícula do estudante (identificador único por campus) |
| Operação por celular e leitor USB | suportada nos navegadores-alvo |

---

## 2. Limites do MVP

### Incluído na versão 0.1

- administração de campus, turmas e estudantes;
- importação de estudantes por CSV e XLSX;
- geração e impressão/exportação de QR Codes;
- cadastro de cardápio simples;
- abertura, operação e encerramento de sessões de distribuição;
- leitura por câmera e por scanner USB (entrada como teclado);
- entrega regular automática;
- bloqueio de duplicidade;
- autorização de entrega excedente com justificativa;
- painel operacional com totais;
- lista de pendentes;
- relatório diário CSV/PDF ou página imprimível;
- autenticação para equipe e perfis de acesso;
- trilha de auditoria e estorno, sem exclusão física de entregas.

### Explicitamente fora do MVP

- estoque, compras, fornecedores, custos e produção;
- integração com sistema acadêmico;
- restrições/alergias, foto e ingredientes detalhados do cardápio;
- portal e login do estudante;
- autenticação Google institucional;
- operação offline e sincronização;
- multi-campus operacional;
- previsão de demanda e BI avançado.

> **Decisão de arquitetura:** manter `campus_id` e `meal_type` desde a primeira migration, embora o primeiro lançamento use um único campus e um tipo de refeição principal.

---

## 3. Papéis e permissões

| Ação | Administrador | Operador PNAE | Gestor |
|---|:---:|:---:|:---:|
| Gerir campus, usuários e parâmetros | ✓ | — | — |
| Importar estudantes, turmas e QR Codes | ✓ | — | — |
| Cadastrar cardápio | ✓ | ✓ | — |
| Criar/abrir/encerrar distribuição | ✓ | ✓ | — |
| Registrar entrega regular | ✓ | ✓ | — |
| Solicitar segunda entrega | ✓ | ✓ | — |
| Autorizar excedente/segunda entrega | ✓ | opcional, conforme permissão individual | — |
| Estornar entrega | ✓ | opcional, conforme permissão individual | — |
| Consultar relatórios e auditoria | ✓ | próprio campus | ✓ |

O perfil Gestor é somente leitura no MVP. A autorização de excedente pode ser uma permissão adicional ao usuário, evitando criar mais um papel cedo demais.

---

## 4. Fluxos críticos

### 4.1 Preparar distribuição

1. Operador cadastra ou seleciona o cardápio do dia.
2. Informa data, tipo de refeição, hora inicial/final prevista e quantidade prevista opcional.
3. O sistema cria uma `Distribuição` em estado **RASCUNHO**.
4. Ao iniciar, muda para **ABERTA** e a tela de leitura é disponibilizada.
5. O sistema calcula os estudantes aptos: ativos, vinculados ao campus e, se aplicável, à turma elegível.

### 4.2 Entrega regular

1. Operador lê token QR ou o scanner USB envia o valor seguido de Enter.
2. Sistema valida o token, encontra estudante ativo e verifica se a distribuição está aberta.
3. Se não houver entrega regular anterior, grava a entrega de tipo `REGULAR` e responde em verde com nome, turma e hora.
4. A tela volta ao estado de leitura sem confirmação manual.
5. O sistema registra o operador e o dispositivo/sessão, quando disponível.

### 4.3 Nova tentativa e excedente

1. Ao ler um estudante que já recebeu `REGULAR`, a interface mostra estado vermelho, a primeira entrega e nenhuma nova entrega é criada.
2. O operador pode cancelar ou selecionar **Solicitar entrega excedente**.
3. O sistema exige usuário com permissão de autorização e motivo padronizado ou texto livre.
4. Após autenticação/reautenticação apropriada, cria uma entrega `EXCEDENTE`, vinculada ao autorizador e à justificativa.
5. A entrega excedente nunca substitui ou apaga a regular.

### 4.4 Correção (estorno)

1. Usuário autorizado abre uma entrega registrada incorretamente.
2. Informa motivo obrigatório.
3. O sistema cria um registro de estorno vinculado à entrega original; não apaga o registro original.
4. Os indicadores operacionais consideram apenas entregas ativas; auditoria e relatórios de controle exibem ambos os eventos.

### 4.5 Encerramento e relatório

1. Operador encerra a distribuição.
2. O sistema congela novos registros regulares e excedentes.
3. Exibe: aptos, regulares válidas, excedentes válidos, pendentes, estornos e taxas.
4. Gestor exporta relatório diário.

---

## 5. Regras de negócio

| ID | Regra |
|---|---|
| RN-01 | Uma distribuição pertence a um campus e a um tipo de refeição. |
| RN-02 | Apenas distribuições no estado `ABERTA` aceitam entregas. |
| RN-03 | Um estudante ativo pode ter no máximo uma entrega `REGULAR` ativa por distribuição. |
| RN-04 | A tentativa duplicada não gera entrega, somente feedback na interface e evento de auditoria opcional. |
| RN-05 | Uma entrega `EXCEDENTE` exige justificativa, operador solicitante e usuário autorizador. |
| RN-06 | A entrega excedente só pode ocorrer enquanto a distribuição estiver aberta e com excedentes liberados ou mediante autorização explícita. |
| RN-07 | QR Code codifica a matrícula do estudante (identificador único por campus); nome, CPF e turma não aparecem codificados. |
| RN-08 | Estudante inativo ou de outro campus não pode receber entrega. |
| RN-09 | Entregas e importações não são apagadas fisicamente; correções usam status e registros de auditoria. |
| RN-10 | Horários são armazenados em UTC e apresentados no fuso do campus. |
| RN-11 | Toda alteração administrativa relevante registra ator, data/hora, entidade, ação, antes/depois quando aplicável. |
| RN-12 | Dados de estudantes e relatórios seguem princípio de mínimo acesso e LGPD; QR não expõe dados pessoais. |

### Estados da distribuição

`RASCUNHO → ABERTA → ENCERRADA`

Opcionalmente, `CANCELADA` a partir de RASCUNHO ou ABERTA, com motivo e registro de auditoria. Uma distribuição encerrada pode ser **reaberta no mesmo dia** (com registro de auditoria); fora do dia, criar nova sessão evita ambiguidade no histórico.

---

## 6. Modelo de dados inicial

```text
CAMPUS
- id, name, code, timezone, active

CLASS_GROUP
- id, campus_id, name, course, academic_year, active

STUDENT
- id, campus_id, registration_number, full_name, email, class_group_id,
  active, created_at, updated_at

USER
- id, campus_id (nullable para administrador global), name, email,
  role, can_authorize_extras, can_reverse_deliveries, active

MENU
- id, campus_id, service_date, meal_type, description, notes,
  created_by, created_at

DISTRIBUTION
- id, campus_id, menu_id (nullable), service_date, meal_type,
  planned_start_at, planned_end_at, status, estimated_quantity,
  extras_enabled_at, extras_enabled_by, opened_by, closed_by,
  opened_at, closed_at

DELIVERY
- id, distribution_id, student_id, delivery_type,
  delivered_at, recorded_by, authorized_by (nullable), reason (nullable),
  status, reversed_at (nullable), reversed_by (nullable), reversal_reason (nullable)

AUDIT_EVENT
- id, campus_id, actor_id (nullable), action, entity_type, entity_id,
  occurred_at, metadata_json

IMPORT_JOB
- id, campus_id, file_name, created_by, created_at, status,
  total_rows, imported_rows, rejected_rows, error_report_path
```

### Restrições importantes no PostgreSQL

- `UNIQUE (campus_id, registration_number)` em estudante;
- índice por `registration_number` (já coberto pelo único por campus);
- índice por `(distribution_id, student_id)` em entrega;
- índice único parcial: uma única entrega `REGULAR` com `status = 'VALIDA'` por `(distribution_id, student_id)`;
- `delivery_type ∈ {REGULAR, EXCEDENTE}`;
- `status ∈ {VALIDA, ESTORNADA}`.

A restrição única parcial deve ser criada no banco, não apenas na interface. Ela protege contra duas leituras concorrentes.

---

## 7. Telas do MVP

| Tela | Usuários | Conteúdo e ação principal |
|---|---|---|
| Login | equipe | e-mail/senha inicialmente; sessão segura |
| Painel inicial | todos | distribuição atual, totais e atalhos por permissão |
| Estudantes | administrador | listar, buscar, ativar/inativar, importar |
| Importar estudantes | administrador | enviar CSV/XLSX, mapear colunas, validar prévia, confirmar e baixar erros |
| QR Codes | administrador | gerar (matrícula do aluno) e exportar folha de impressão |
| Cardápios | admin/operador | cadastrar data, tipo, descrição e observação |
| Distribuições | admin/operador | criar, abrir, encerrar, visualizar histórico |
| Operação de entrega | operador | campo focado para scanner, botão de câmera, feedback grande, totais ao vivo |
| Autorização de excedente | autorizado | confirma aluno, mostra primeira entrega, exige motivo e registra autorizador |
| Pendentes | operador/gestor | estudantes aptos sem entrega regular válida; filtro por turma |
| Relatório diário | operador/gestor | totais, detalhamento, pendentes e exportação |
| Auditoria | admin/gestor | filtros por data, usuário, entidade e ação |

### Comportamento obrigatório da tela de operação

- o campo de leitura inicia focado e recupera foco após cada resposta;
- suporte a câmera via `getUserMedia` quando o navegador permitir;
- scanner USB funciona como teclado, recebendo token + Enter;
- feedback visual, textual e sonoro opcional é inequívoco: verde para entregue, vermelho para duplicidade, amarelo para QR inválido;
- não mostrar dados além do necessário; nome, turma e matrícula podem aparecer para reduzir erro operacional;
- registrar o resultado antes de exibir “entregue”.

---

## 8. API proposta

Autenticação baseada em sessão segura ou JWT com expiração curta. A versão inicial pode usar páginas Django/HTMX e expor endpoints JSON apenas onde a leitura assíncrona exigir.

| Método e rota | Finalidade |
|---|---|
| `POST /api/auth/login` | autenticar equipe |
| `GET /api/distributions/current` | obter distribuição aberta do campus |
| `POST /api/distributions` | criar rascunho |
| `POST /api/distributions/{id}/open` | abrir distribuição |
| `POST /api/distributions/{id}/close` | encerrar distribuição |
| `POST /api/distributions/{id}/scan` | receber token QR e tentar entrega regular de modo atômico |
| `POST /api/distributions/{id}/extras` | registrar excedente autorizado |
| `POST /api/deliveries/{id}/reverse` | estornar entrega |
| `GET /api/distributions/{id}/summary` | totais e indicadores ao vivo |
| `GET /api/distributions/{id}/pending` | estudantes pendentes, com filtros |
| `GET /api/distributions/{id}/report` | relatório/exportação |
| `POST /api/students/imports` | enviar arquivo para validação/importação |
| `GET /api/students/qr-export` | exportar QR Codes |

### Contrato de resposta da leitura

A resposta de `POST /scan` deve tornar a interface determinística:

```json
{
  "result": "DELIVERED | ALREADY_DELIVERED | INVALID_TOKEN | INELIGIBLE | DISTRIBUTION_CLOSED",
  "student": {"id": "...", "name": "...", "registrationNumber": "...", "className": "..."},
  "delivery": {"id": "...", "type": "REGULAR", "deliveredAt": "..."},
  "previousDelivery": null,
  "message": "Entrega registrada"
}
```

Para duplicidade, `previousDelivery` contém ao menos data/hora e tipo da entrega anterior. Nunca retornar token QR nem dados sensíveis desnecessários.

---

## 9. Arquitetura recomendada

### Escolha para o MVP

- **Backend e páginas:** Django 5 + Python.
- **Banco:** PostgreSQL.
- **UI:** Django templates + HTMX + Tailwind CSS.
- **Geração de QR:** biblioteca Python; o conteúdo é a matrícula do estudante.
- **PWA:** manifesto, ícones, HTTPS e cache somente de recursos estáticos inicialmente.
- **Hospedagem:** container Docker, aplicação web e PostgreSQL gerenciado ou com backup automatizado.

### Por que esta escolha

Django Admin reduz o esforço de administração de estudantes, usuários, turmas e cardápios. Templates/HTMX mantêm o fluxo de scanner rápido sem introduzir a complexidade inicial de uma SPA. PostgreSQL permite garantir a entrega única com restrição transacional real.

### Não implementar agora

- fila e sincronização offline;
- microsserviços;
- aplicativo nativo;
- front-end React separado;
- autorização sofisticada por workflow.

---

## 10. Segurança, LGPD e operação

1. Usar HTTPS em todos os ambientes não locais.
2. QR Code codifica a matrícula do estudante; a matrícula é identificador, **não** segredo, e por isso a antifraude se apoia em aluno ativo, escopo de campus e entrega regular única por distribuição.
3. Senhas com hash forte gerenciado pelo Django; nunca registrar senha ou dados pessoais em logs.
4. Aplicar autorização por campus em toda consulta e mutação.
5. Implementar backups testados do banco e política de retenção definida pelo campus.
6. Exportações devem exigir permissão e conter somente colunas necessárias.
7. Definir responsável institucional pelo tratamento dos dados e base legal antes de produção.
8. Registrar auditoria sem armazenar informação excessiva nos metadados.
9. Realizar teste de concorrência: duas leituras simultâneas do mesmo QR devem resultar em exatamente uma entrega regular válida.

---

## 11. Plano de entregas

### Marco 0 — Descoberta e decisões (1 a 3 dias)

- validar processo real no refeitório: picos, operadores, dispositivos, conectividade e exceções;
- obter amostra anonimizada da planilha atual;
- confirmar campos mínimos de estudante e convenção de turma;
- decidir quem pode autorizar excedentes/estornos;
- definir nomenclatura de refeições e formato do relatório diário;
- aprovar protótipo navegável da tela de operação.

**Saída:** backlog priorizado, critérios de aceite e dados de importação definidos.

### Marco 1 — Fundamentos (3 a 5 dias)

- projeto Django, usuários/papéis, campus, turmas, estudantes e migrations;
- importação CSV/XLSX com relatório de linhas rejeitadas;
- geração de tokens e exportação de QR;
- admin e trilha de auditoria inicial.

**Aceite:** importar uma base de teste, localizar estudante, imprimir QR e impedir matrícula duplicada.

### Marco 2 — Núcleo de distribuição (4 a 6 dias)

- cardápios, distribuições e estados;
- API/fluxo atômico de leitura;
- tela otimizada para scanner USB e câmera;
- indicadores de entregues/pendentes;
- teste concorrente de duplicidade.

**Aceite:** realizar simulação de pelo menos 50 leituras, com entrega correta, duplicidade bloqueada e totais coerentes.

### Marco 3 — Excedentes, correção e relatório (3 a 5 dias)

- autorização com motivo;
- estorno auditável;
- lista de pendentes e filtros por turma;
- relatório diário exportável/imprimível.

**Aceite:** relatório reconcilia entregas regulares, excedentes e estornos com o histórico de eventos.

### Marco 4 — Piloto e estabilização (5 a 10 dias, conforme operação)

- homologação com dados reais controlados;
- ensaio operacional e treinamento curto;
- piloto em uma distribuição;
- correções de usabilidade e publicação.

**Aceite de produção:** operador consegue operar sem apoio técnico; há backup e procedimento de contingência documentado.

> Estimativa indicativa: 3 a 5 semanas de calendário para um MVP bem testado, variando com disponibilidade de dados, decisões institucionais, ambiente de hospedagem e piloto.

---

## 12. Backlog priorizado

### P0 — indispensável para o piloto

- [ ] Usuários, papéis e isolamento por campus
- [ ] Turmas e estudantes ativos
- [ ] Importação CSV/XLSX com validação
- [ ] QR Code com a matrícula, geração e exportação
- [ ] Cardápio simples
- [ ] Criar, abrir e encerrar distribuição
- [ ] Leitura USB/câmera e entrega regular automática
- [ ] Bloqueio transacional de duplicidade
- [ ] Autorização de excedente com motivo
- [ ] Painel de totais e pendentes
- [ ] Relatório diário
- [ ] Auditoria e estorno
- [ ] Backup, HTTPS e logs seguros

### P1 — imediatamente após piloto

- [ ] Login Google institucional
- [ ] Cardápio semanal
- [ ] Histórico e QR no portal do estudante
- [ ] Indicadores por turma
- [ ] Impressão mais flexível de crachás/folhas QR
- [ ] Melhorias de acessibilidade e atalhos de teclado

### P2 — somente após comprovar o núcleo

- [ ] Offline/sincronização
- [ ] Multi-campus pleno
- [ ] Integração acadêmica
- [ ] Estoque, sobras, perdas e custos
- [ ] Restrições alimentares
- [ ] Previsão de demanda e BI

---

## 13. Riscos e mitigação

| Risco | Impacto | Mitigação inicial |
|---|---|---|
| QR esquecido, danificado ou inacessível | fila e exclusão indevida | busca manual por matrícula/nome, com o mesmo bloqueio de duplicidade |
| Scanner/câmera instável | lentidão | homologar dispositivos; manter campo USB como caminho primário |
| Internet indisponível | operação para | procedimento manual temporário e reconciliação; offline fica no pós-MVP |
| Dados de importação inconsistentes | estudantes ausentes/duplicados | prévia de validação, relatório de erros e aprovação antes de aplicar |
| Dupla leitura simultânea | entrega duplicada | transação e índice único parcial no PostgreSQL |
| Uso indevido de excedente | perda de rastreabilidade | autorização, motivo obrigatório e relatório separado |
| Exposição de dados pessoais | risco LGPD | QR opaco, permissões, HTTPS, minimização e auditoria |

---

## 14. Decisões que precisam de validação institucional

1. Qual será o campus inicial e quais tipos de refeição entrarão no piloto?
2. Qual fonte é oficial para estudantes, matrícula, turma e situação ativa?
3. Quais formatos reais de CSV/XLSX a equipe possui?
4. Quem autoriza excedentes e estornos? A autorização deve ser por login individual ou PIN/reautenticação?
5. Pode haver entrega para visitante, servidor ou estudante sem QR? Se sim, qual identificação e regra?
6. Um estudante pode retirar mais de uma refeição no mesmo dia, desde que em sessões/tipos distintos?
7. Qual período de retenção será adotado para entregas e auditoria?
8. Onde o sistema será hospedado e quem manterá backups/contas administrativas?
9. O relatório diário precisa de assinatura, layout institucional ou exportação específica?
10. Quais dispositivos estarão disponíveis no ponto de distribuição?

---

## 15. Definição de pronto do MVP

O MVP está pronto para piloto quando todos os itens abaixo forem verdadeiros:

- uma base real de teste é importada sem duplicidades não tratadas;
- QR Codes são gerados e lidos por ao menos um celular e um scanner USB homologado;
- uma entrega regular é registrada em uma distribuição aberta;
- uma segunda entrega regular simultânea ou repetida é bloqueada pelo banco;
- uma entrega excedente só é criada com autorização e motivo;
- estorno preserva o histórico;
- totais de painel e relatório diário batem com as entregas válidas;
- usuários sem permissão não conseguem acessar dados ou ações administrativas;
- backup e restauração foram testados ao menos uma vez;
- o fluxo foi ensaiado com operadores antes do primeiro uso real.
