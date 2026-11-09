# Painel de Cotações & Clima — Projeto 4

Aplicação Django que consome a AwesomeAPI, guarda cotações no SQLite, expõe o
histórico por uma API REST e desenha sua variação no navegador. Também pode
mostrar o clima atual da cidade configurada usando a OpenWeatherMap.

## Funcionalidades

- Consulta de vários pares de moedas em uma única requisição:
  USD/BRL, EUR/BRL, GBP/BRL, BTC/BRL, USD/EUR, EUR/USD, BTC/USD e BTC/EUR.
- Cache em memória das cotações por 5 minutos para evitar chamadas externas
  repetidas; o cache armazena valores por par e por URL de API configurada.
- Persistência das consultas novas usando `DecimalField`.
- Histórico JSON em `/api/historico/`, somente leitura, limitado aos 500
  registros mais recentes.
- Tabela dinâmica e gráfico interativo com Chart.js, ambos alimentados por
  `fetch()` e pela API do próprio projeto.
- Clima atual da cidade configurada, com cache de 10 minutos. A chave da
  OpenWeatherMap é opcional; sem ela, o painel informa como habilitar o recurso.
- Comando Django para consultar os pares periodicamente sem depender de uma
  requisição de navegador.
- Django Admin para visualizar os registros.
- Testes automatizados que simulam as APIs e podem ser executados offline.

## Requisitos

- Python 3.10 ou superior.
- Acesso à internet para consultar as APIs e carregar o Chart.js.
- Uma chave gratuita da OpenWeatherMap para habilitar o cartão de clima.

## Como executar no Windows (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Abra <http://127.0.0.1:8000/>. A aplicação consulta USD/BRL por padrão; marque
um ou mais pares e use **Consultar cotações** para selecionar outros.

Se o PowerShell bloquear a ativação do ambiente virtual, execute
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` no terminal atual
e tente ativá-lo novamente.

## Capturas de tela

![Painel com múltiplos pares, gráfico e histórico](screenshots/painel.png)

![Django Admin com os registros de cotação](screenshots/admin.png)

## Clima e variáveis de ambiente

Crie uma chave no painel da OpenWeatherMap e configure-a no terminal antes de
iniciar o Django. Defina também a cidade (Brasília é o padrão):

```powershell
$env:OPENWEATHERMAP_API_KEY = "sua-chave"
$env:WEATHER_CITY = "Brasília,BR"
python manage.py runserver
```

Não publique a chave, não a adicione ao código-fonte e não a envie ao GitHub.
`.env.example` lista as variáveis esperadas, mas não é carregado
automaticamente pelo Django. Configure-as no ambiente que inicia o servidor.

Outras configurações:

- `COTACAO_URL`: endpoint AwesomeAPI compatível com `/last/PAIR`; o padrão
  permite consultar pares múltiplos.
- `DJANGO_SECRET_KEY`: segredo Django; use um valor próprio fora do ambiente
  local.
- `DJANGO_DEBUG`: defina `false` em produção.
- `DJANGO_ALLOWED_HOSTS`: nomes de host permitidos separados por vírgula.

## Rotas

| Rota | Método | Descrição |
| --- | --- | --- |
| `/` ou `/consultar/` | GET | Consulta os pares selecionados e mostra clima, histórico e gráfico |
| `/api/historico/` | GET | Retorna até 500 registros recentes em JSON |
| `/admin/` | — | Administração dos registros e usuários do Django |

Para criar uma conta de administração, use `python manage.py createsuperuser`.

## Cache

As cotações ficam em cache por 300 segundos e o clima por 600 segundos. O cache
padrão do Django é local ao processo; reiniciar o servidor o limpa. A cada
cotação realmente nova, o projeto salva um registro, sem duplicar o histórico
quando uma cotação ainda está no cache. Para trocar ou desabilitar o cache,
configure um backend apropriado em `CACHES`.

## Consultas agendadas

O comando abaixo consulta os pares disponíveis e salva os valores novos. Ele
pode ser executado manualmente ou agendado pelo sistema operacional:

```powershell
python manage.py consultar_cotacoes
```

No Windows, abra o **Agendador de Tarefas** e crie uma tarefa básica com gatilho
repetido a cada 30 minutos. Configure a ação **Iniciar um programa** assim:

- **Programa/script:** caminho completo para o `python.exe` do ambiente `.venv`,
  por exemplo `C:\caminho\Projeto4\.venv\Scripts\python.exe`.
- **Adicionar argumentos:** `manage.py consultar_cotacoes`
- **Iniciar em:** caminho completo da pasta que contém `manage.py`.

Configure também `COTACAO_URL` na tarefa se estiver usando um endpoint próprio.
No Linux, por exemplo, a mesma tarefa pode ser configurada no cron:

```cron
*/30 * * * * cd /caminho/Projeto4 && /caminho/Projeto4/.venv/bin/python manage.py consultar_cotacoes
```

## Banco de dados e migrations

O SQLite é usado por padrão e o arquivo `db.sqlite3` é criado localmente.
Depois de alterar os models, gere e aplique migrations:

```powershell
python manage.py makemigrations
python manage.py migrate
```

## Testes

```powershell
python manage.py test
```

Os testes mockam as chamadas externas, portanto não precisam da AwesomeAPI nem
da chave OpenWeatherMap. Cobrem consulta múltipla, cache, erros, API do
histórico, clima e comando agendado.

## Publicação e segurança

Não publique o ambiente virtual, o banco local, arquivos `.env` nem chaves de
API. O `SECRET_KEY` padrão serve apenas para desenvolvimento. Em produção,
defina `DJANGO_SECRET_KEY`, configure `DJANGO_DEBUG=false` e informe os hosts
permitidos em `DJANGO_ALLOWED_HOSTS`.
