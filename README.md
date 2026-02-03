# Portal da Transparência - Scraper & Dashboard

Sistema automático para coletar dados do Portal da Transparência de Fortaleza e visualizar em dashboard interativo.

## :information_source: Sobre o Projeto

Este projeto:
1. **Coleta dados** diários do Portal da Transparência de Fortaleza via API
2. **Armazena** em banco de dados SQLite (acumulativo)
3. **Visualiza** em dashboard interativo com Streamlit
4. **Agenda** execução automática todos os dias

## :rocket: Funcionalidades

- Download automático de despesas detalhadas (Empenho, Liquidação, Pagamento)
- Armazenamento em banco SQLite local
- Dashboard interativo com filtros e gráficos
- Exportação para CSV
- Execução agendada diária

## :file_folder: Estrutura do Projeto

```
portal-scraper/
├── scraper.py          # Script principal de coleta de dados
├── dashboard.py        # Dashboard Streamlit
├── scheduler.py        # Agendador de execução automática
├── requirements.txt    # Dependências Python
├── data/              # Diretório de dados
│   └── despesas.db    # Banco SQLite
├── logs/              # Logs de execução
└── README.md          # Este arquivo
```

## :wrench: Instalação

### 1. Criar ambiente virtual

```bash
cd /Users/tiago/portal-scraper
python3 -m venv venv
source venv/bin/activate
```

### 2. Instalar dependências

```bash
pip install -r requirements.txt
```

## :play_button: Uso

### Execução única (baixar dados de ontem)

```bash
python scraper.py
```

### Executar com dados históricos (últimos 30 dias)

Adicione ao final do `scraper.py`:

```python
if __name__ == "__main__":
    api = PortalTransparenciaAPI()
    db = DatabaseManager()
    baixar_dados_anteriores(db, api, dias=30)
```

### Iniciar Dashboard

```bash
streamlit run dashboard.py
```

O dashboard estará disponível em: http://localhost:8501

### Execução Automática Diária

```bash
python scheduler.py
```

O scheduler executará automaticamente às 6:00 da manhã todos os dias.

## :calendar: Agendamento com Cron (recomendado)

Para execução automática no macOS/Linux:

```bash
# Editar crontab
crontab -e

# Adicionar linha (executa todos os dias às 6:00)
0 6 * * * cd /Users/tiago/portal-scraper && /usr/bin/python3 scraper.py >> logs/cron.log 2>&1
```

Ou usar launchd no macOS:

```bash
# Criar arquivo ~/Library/LaunchAgents/com.user.portal-scraper.plist
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.portal-scraper</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/Users/tiago/portal-scraper/scraper.py</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>6</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>WorkingDirectory</key>
    <string>/Users/tiago/portal-scraper</string>
    <key>StandardOutPath</key>
    <string>/Users/tiago/portal-scraper/logs/scheduler.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/tiago/portal-scraper/logs/scheduler.log</string>
</dict>
</plist>
```

Carregar o agente:
```bash
launchctl load ~/Library/LaunchAgents/com.user.portal-scraper.plist
```

## :chart_with_upwards_trend: Dashboard

O dashboard oferece:

- **Resumo Geral**: Totais empenhado, liquidado e pago
- **Evolução Diária**: Gráfico de linha com pagamentos por dia
- **Top Órgãos**: Ranking de órgãos por valor pago
- **Por Fase**: Distribuição empenho x liquidação x pagamento
- **Tabela Detalhada**: Dados completos com filtros

### Filtros Disponíveis

- Fase da despesa (Empenho, Liquidação, Pagamento)
- Órgão específico
- Período de datas

## :computer: API Direta

O sistema utiliza a API do Portal da Transparência:

```
GET https://portaltransparencia-back.sepog.fortaleza.ce.gov.br/api/despesas/detalhadas/diarias/{data_inicio}/{data_fim}/{fase}
```

Parâmetros:
- `data_inicio`: DD-MM-YYYY
- `data_fim`: DD-MM-YYYY
- `fase`: empenho, liquidacao, ou pagamento

## :database: Banco de Dados

Estrutura da tabela `despesas`:

| Campo | Tipo | Descrição |
|-------|------|-----------|
| api_id | INTEGER | ID único da API |
| exercicio | INTEGER | Ano do exercício |
| data_pagamento | TEXT | Data do pagamento |
| fase | TEXT | Fase da despesa |
| favorecido | TEXT | Nome do credor |
| orgao | TEXT | Órgão responsável |
| valor_pago | REAL | Valor pago |
| ... | ... | Outros campos |

## :warning: Troubleshooting

**Erro: Banco de dados não encontrado**
- Execute `python scraper.py` pela primeira vez para criar o banco

**Erro: Nenhum dado disponível**
- Verifique se a API está acessível
- Confira o log em `logs/scraper.log`

**Dashboard não carrega**
- Verifique se o arquivo `data/despesas.db` existe
- Execute `streamlit run dashboard.py` no diretório do projeto

## :books: Referências

- Portal da Transparência de Fortaleza: https://portaltransparencia.fortaleza.ce.gov.br
- Streamlit: https://streamlit.io
