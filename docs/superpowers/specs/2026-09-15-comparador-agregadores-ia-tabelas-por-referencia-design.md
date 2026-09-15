# Comparador de agregadores de IA (Hubsia)

Site pessoal, protegido por um secret, para comparar planos de agregadores de IA. Cada tabela responde uma pergunta do tipo: “nessa geração de referência, quantos vídeos cabem no dólar e no mês?”. O primeiro recorte de interesse é Wan 3, 10 s, 480p, mas a referência é por tabela e pode mudar.

## Objetivo

O usuário informa, por serviço, o preço do plano, os créditos do mês e quantos créditos custa a geração de referência. O site calcula créditos por dólar, gerações por dólar e gerações mensais no plano, e guarda isso no servidor para acesso pelo tablet, celular e computador.

## Fora de escopo (v1)

- Contas, e-mail, papéis ou tabelas isoladas por pessoa
- Catálogo compartilhado de planos entre tabelas (cada tabela tem as próprias linhas)
- Destacar automaticamente o “melhor” custo, ordenação clicável, gráficos
- App nativo, PWA, sync offline
- CSRF token dedicado (mitigação no v1: cookie `HttpOnly` + `SameSite=Lax` + HTTPS)
- Docker (o README descreve Uvicorn + proxy HTTPS; container fica para depois)

## Stack

- Python 3.12+, FastAPI, Uvicorn, Jinja2, HTML/CSS (sem SPA)
- SQLite em arquivo persistente na VPS
- Autenticação: um único secret em variável de ambiente
- Testes: pytest + `httpx`/`TestClient`

O processo Python entrega as páginas e os POSTs. Na VPS, Nginx ou Caddy faz HTTPS e encaminha para o Uvicorn em `127.0.0.1`.

## Autenticação

Um único segredo: `HUBSIA_SECRET` (nunca no frontend).

Fluxo:

1. `GET /login` — campo senha.
2. `POST /login` — comparação em tempo constante com `HUBSIA_SECRET`. Erro: permanece no login com mensagem “Secret inválido.”. Acerto: cookie de sessão assinado com o mesmo secret, redirect para a lista de comparações.
3. Qualquer outra rota sem cookie válido: redirect para `/login` (HTML e POST).
4. `POST /logout` — apaga o cookie, volta ao login.
5. `GET /login` com sessão já válida — redirect para `/`.

Cookie: nome `hubsia_session`, `HttpOnly`, `SameSite=Lax`, `Secure` quando `HUBSIA_HTTPS=true` (caso da VPS atrás de HTTPS). Duração: 30 dias. Sem botão “lembrar-me”; quem tem o secret entra e permanece até logout ou expiração.

Layout autenticado (`pagina_base_hubsia.html`): link “Comparações” para `/` e botão/form “Sair” (`POST /logout`).

Quem conhece o secret vê a mesma base. Não há usuários.

## Modelo de dados

SQLite, caminho `HUBSIA_DB_PATH` (default: `data/hubsia.db`).

### `comparacoes`

| Coluna | Tipo | Regras |
|---|---|---|
| `id` | INTEGER PK | autoincrement |
| `nome` | TEXT | obrigatório, 1–80 caracteres, nome curto na lista |
| `referencia` | TEXT | obrigatório, 1–200 caracteres, o que está sendo comparado (ex.: “Wan 3, 10s, 480p”) |
| `criado_em` | TEXT | ISO-8601 UTC na criação |
| `atualizado_em` | TEXT | ISO-8601 UTC a cada edição |

Apagar uma comparação apaga em cascata os serviços dela.

### `servicos`

| Coluna | Tipo | Regras |
|---|---|---|
| `id` | INTEGER PK | autoincrement |
| `comparacao_id` | INTEGER FK | not null, `ON DELETE CASCADE` |
| `nome` | TEXT | obrigatório, 1–80 caracteres; nomes repetidos são permitidos (planos diferentes do mesmo agregador) |
| `custo_mensal_usd` | REAL | obrigatório, número > 0 |
| `creditos_mes` | REAL | obrigatório, número > 0 |
| `custo_referencia_creditos` | REAL | obrigatório, número > 0 |

Não há unicidade de nome. Não há catálogo global de serviços.

## Cálculos

Módulo puro `calculos_creditos_e_geracoes_por_dolar.py`, usado pela renderização e pelos testes. Entrada: `custo_mensal_usd`, `creditos_mes`, `custo_referencia_creditos` (todos `Decimal`). Saída:

- `creditos_por_dolar = creditos_mes / custo_mensal_usd`
- `geracoes_mensais = creditos_mes / custo_referencia_creditos`
- `geracoes_por_dolar = geracoes_mensais / custo_mensal_usd`

Equivalência obrigatória: `geracoes_por_dolar == creditos_por_dolar / custo_referencia_creditos`.

Se qualquer entrada for ≤ 0, a função levanta erro de validação; a rota não persiste e devolve o formulário com mensagem no campo.

Exemplo canônico (Higgsfield): 30 USD, 1200 créditos, 10 créditos por geração → créditos/US$ = 40, gerações no mês = 120, gerações/US$ = 4.

Cálculo interno mantém `Decimal` sem arredondar. Exibição: locale pt-BR; se o valor for inteiro, sem casas (1200, 4, 40); senão `quantize` com `ROUND_HALF_UP` em 2 casas (3,333… → 3,33). Inputs numéricos: `type="number" step="any"`; no servidor, aceitar vírgula ou ponto decimal (trocar `,` por `.` antes do `Decimal`).

## Telas

Idioma da UI: português do Brasil. `viewport` mobile. Formulários empilhados em tela estreita; tabela com `overflow-x: auto`.

### Login

Uma coluna: título Hubsia, campo senha, botão Entrar.

### Lista de comparações — `GET /`

Lista `nome` (e um trecho da `referencia`). Ações: abrir, excluir (confirmação). Botão “Nova comparação”. Estado vazio: “Nenhuma comparação ainda.” + atalho para criar.

### Nova / editar metadados da comparação

Campos: nome, referência. Criar redireciona para a tabela vazia. Na página da tabela, os mesmos dois campos podem ser salvos de novo.

Ao salvar uma `referencia` **diferente** da anterior: o POST redireciona (PRG) e a mensagem flash vai na sessão/cookie, exibida uma vez no GET seguinte — “A referência mudou. Atualize o custo em créditos de cada serviço para a nova geração.” Os números das linhas não são recalculados nem apagados. Trocar só o `nome` da comparação não dispara esse aviso.

### Tabela da comparação — `GET /comparacoes/{id}`

Topo: nome + “Comparando: {referencia}”.

Formulário de serviço (4 campos): serviço, custo mensal (USD), créditos no mês, custo da geração de referência (créditos). POST cria linha e recarrega a tabela. Se `?editar_servico={id}`, o mesmo formulário vem preenchido e o POST atualiza aquela linha; link Cancelar volta à criação.

Tabela (7 colunas):

1. Serviço
2. Custo mensal (USD)
3. Total de créditos no mês
4. Créditos por dólar *(calculado)*
5. Custo usado como referência
6. Gerações por dólar *(calculado)*
7. Gerações mensais no plano *(calculado)*

Colunas 4, 6 e 7 nunca são inputs. Cada linha: Editar e Excluir (excluir com `confirm()` nativo). Estado vazio: “Nenhum serviço ainda.”

404 se o id não existir: página simples + link para a lista.

## Rotas

Todas as rotas abaixo, exceto login, exigem sessão.

| Método | Caminho | Função |
|---|---|---|
| GET | `/login` | formulário do secret |
| POST | `/login` | valida secret, seta cookie |
| POST | `/logout` | limpa cookie |
| GET | `/` | lista comparações |
| GET | `/comparacoes/nova` | form nova comparação |
| POST | `/comparacoes` | cria comparação |
| GET | `/comparacoes/{id}` | tabela + form de serviço |
| POST | `/comparacoes/{id}` | atualiza nome e referência |
| POST | `/comparacoes/{id}/excluir` | apaga comparação e serviços |
| POST | `/comparacoes/{id}/servicos` | cria serviço |
| POST | `/servicos/{id}` | atualiza serviço (a comparação é a do próprio registro) |
| POST | `/servicos/{id}/excluir` | apaga serviço |

GET em rotas só-POST: 405. Sem JSON no v1: HTML + redirect após POST (padrão Post/Redirect/Get).

## Validação e erros

- Secret inválido: 200 no login com erro (não revelar se o secret “existe”).
- Campos vazios ou números não-finitos / ≤ 0: 422 renderizando o mesmo formulário (exceção ao PRG), sem gravar.
- Comparação ou serviço inexistente: 404 HTML.
- Sem sessão: 302 para `/login`.
- Exclusões só via POST.

## Persistência e deploy

- Criar o arquivo SQLite e as tabelas na primeira subida se não existirem.
- README: `HUBSIA_SECRET`, `HUBSIA_HTTPS`, `HUBSIA_DB_PATH`, comando `uvicorn aplicacao_fastapi_comparador_agregadores:app --host 127.0.0.1 --port 8000`, exemplo de reverse proxy, lembrete de backup = copiar o `.db`.
- Bind público do Uvicorn não é o modo documentado; o proxy é que escuta 443.

## Testes

Testes usam `HUBSIA_SECRET` próprio (não o da VPS), banco SQLite temporário por teste, `HUBSIA_HTTPS` desligado.

1. Unidade de `calculos_creditos_e_geracoes_por_dolar.py`: exemplo Higgsfield; equivalência das duas formas de gerações/US$; rejeição de zero e negativo; formatação pt-BR (inteiro sem casas; `ROUND_HALF_UP` em 2 casas).
2. Rotas com `TestClient`: login recusado e aceito; CRUD de comparação; CRUD de serviço; recálculo visível no HTML da tabela; recusa sem cookie; exclusão em cascata; aviso de referência só quando o texto da referência muda.

Rodar `pytest` depois de criar ou alterar esses testes.

## Estrutura de arquivos (v1)

```
hubsia/
  README.md
  requirements.txt
  calculos_creditos_e_geracoes_por_dolar.py
  banco_sqlite_comparacoes_e_servicos.py
  aplicacao_fastapi_comparador_agregadores.py
  templates/
    pagina_base_hubsia.html
    pagina_login_secret.html
    pagina_lista_comparacoes.html
    pagina_formulario_nova_comparacao.html
    pagina_tabela_comparacao_servicos.html
  static/
    estilos_comparador_agregadores.css
  tests/
    test_calculos_creditos_e_geracoes_por_dolar.py
    test_rotas_autenticacao_e_crud_comparacoes.py
  data/          # hubsia.db em runtime; gitignore
```

Arquivos na raiz do projeto (sem pacote `app/`). Uvicorn aponta para `aplicacao_fastapi_comparador_agregadores:app`.

## Critério de pronto

- Com o secret, dá para criar duas comparações com referências diferentes, cadastrar o mesmo agregador em ambas com custos de referência distintos, e ver vencedores diferentes nas colunas calculadas.
- Sem o secret, nenhuma leitura nem escrita.
- `pytest` verde.
- Layout usável em viewport ~390px de largura (form empilhado, tabela com scroll horizontal).
