# Relatório de erros e ajustes do guia passo a passo

**Projeto:** Painel de Cotações & Clima — Projeto 4
**Data da revisão:** 09/11/2026

Este relatório separa os limites dos exemplos do guia original, os defeitos
encontrados enquanto os recursos foram implementados e os pré-requisitos
externos. Os exemplos básicos não são tratados como erros quando correspondem
ao escopo didático daquela etapa.

## Achados e correções

| Origem | Achado | Impacto | Correção e verificação |
| --- | --- | --- | --- |
| Guia, seção “Múltiplas moedas” (páginas 5 e 14) | O model básico usa `DecimalField(max_digits=10, decimal_places=4)`. Isso deixa somente 6 dígitos inteiros; cotações de criptomoedas podem ultrapassar esse limite. O próprio desafio recomenda aumentar `max_digits`. | Uma cotação alta pode exceder a coluna e falhar ao salvar. | O projeto usa `max_digits=18` e a migration correspondente. Um teste grava `12345678901234.1234` e `makemigrations --check` confirma que não há alterações pendentes. |
| Implementação, testes do clima | Os testes substituíam `requests.get` pelo módulo compartilhado `requests`; assim, o mock do clima também interceptava a consulta à AwesomeAPI feita pela mesma view. | Dois testes falhavam pela ordem ou quantidade inesperada de chamadas externas. | O mock agora fornece uma resposta separada para cada API, e os 18 testes passam. |
| Implementação, gráfico | O Chart.js com altura responsiva não tinha uma altura definida no contêiner. Ao tentar adaptar o canvas ao pai sem altura, o navegador expandia o gráfico indefinidamente. | Gráfico excessivamente alto e página difícil de usar. | Cada cartão de gráfico tem altura limitada e cada par possui uma escala própria. A renderização foi conferida no navegador. |
| Inicialização e documentação | O roteiro deixava a porta padrão do Django implícita (`8000`), mas o projeto deve ser aberto em `8005`. | Os comandos e o endereço acessado podiam divergir da porta solicitada. | O README inicia o servidor com `python manage.py runserver 127.0.0.1:8005` e usa `http://127.0.0.1:8005/`. |
| Página inicial | A raiz já encaminhava para o painel, mas não havia links diretos para seus recursos principais. | Era necessário rolar a página ou digitar a URL da API/Admin. | A página inicial ganhou atalhos para consulta, gráfico, histórico JSON e Administração. |

## Configurações externas que não são erros de código

- **Clima:** o projeto usa a OpenWeatherMap. Sem `OPENWEATHERMAP_API_KEY`, o
  painel mostra como configurar a integração e continua exibindo as cotações.
  A chamada é coberta por testes mockados; uma chave real não foi fornecida,
  portanto a integração com credenciais reais não foi testada nesta revisão.
- **Chart.js:** o gráfico carrega a biblioteca pelo CDN; é necessária conexão à
  internet para baixar a biblioteca no navegador.
- **Agendamento:** o comando Django pode ser executado manualmente; a execução
  recorrente depende do Agendador de Tarefas ou do cron do sistema operacional.

## Validação executada

- `python manage.py check`: sem problemas.
- `python manage.py makemigrations --check --dry-run`: nenhuma migration pendente
  após gerar a migration para o aumento de precisão.
- `python manage.py test`: 18 testes aprovados.
- Consulta dos pares de moedas via AwesomeAPI e verificação da interface no
  navegador.
