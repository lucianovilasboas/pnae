# Changelog

Todas as mudanças relevantes deste projeto são registradas aqui.

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/)
e versionamento [SemVer](https://semver.org/lang/pt-BR/).
A versão corrente é a constante `APP_VERSION` em `config/version.py`.

## [1.2.0] - 2026-10-10

### Added
- Sugestões de motivo no excedente e no estorno (`<datalist>`), mantendo o campo
  livre; o que o usuário digita é memorizado no aparelho (`localStorage`, até 10
  por campo) para reutilizar depois.

## [1.1.0] - 2026-10-10

### Added
- Página **Campus ativo** (`/campus/`) e chip de campus no cabeçalho; só quem
  não tem campus vinculado (administrador global) pode trocar.
- `ActiveCampusMiddleware`: leva para a escolha de campus quando o contexto é
  ambíguo (usuário sem campus e mais de um campus ativo).

### Changed
- O campus passa a ser **contexto do usuário** (`resolve_campus`): campus do
  cadastro → campus da sessão (admin global) → informado → único ativo.
  Os formulários deixam de pedir campus.
- Navegação: "Importar" deixa de ser aba e vira ação dentro de **Estudantes**
  ("Importar estudantes"). "QR Codes" permanece separado.

### Removed
- Seletor de campus nos formulários de distribuição e de cardápios.

## [1.0.0] - 2026-10-10

### Added
- Versão do sistema exibida no rodapé (desktop) e no menu (mobile).
- `CHANGELOG.md` para acompanhar as versões.
- Botão "+" ao lado do campo Cardápio que abre um **pop-up** para cadastrar um
  cardápio único sem sair da tela (preserva os valores já preenchidos); ao
  salvar, o cardápio novo entra no select.
- Seletor de campus para administrador global quando há mais de um campus
  ativo (nas telas de Distribuições e de Cardápios).

### Changed
- Tela de Distribuições: **Data**, **Início previsto** e **Fim previsto** na
  1ª linha; **Refeição** e **Cardápio (opcional)** na 2ª linha — layout mais
  compacto.
- Início/Fim previstos agora exibem apenas o horário (a data vem do campo
  Data); a mesma simplificação foi aplicada à edição do rascunho.
- A ação "Cadastrar cardápio" deixou de ficar ao lado de "Criar rascunho" e
  passou para junto do campo Cardápio.

### Fixed
- Erro "Campus não definido." ao cadastrar cardápio por administrador global
  em base com mais de um campus ativo.
