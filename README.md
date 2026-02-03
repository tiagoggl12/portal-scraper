# 🏢 Portal da Transparência de Fortaleza

<!-- DASHBOARD LINK -->
<div align="center">

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://huggingface.co/spaces/tiagoggl12/portal-transparencia-fortaleza)

### 👉 **[Acessar Dashboard](https://huggingface.co/spaces/tiagoggl12/portal-transparencia-fortaleza)** 👈

*Dados atualizados diariamente às 3:00 AM (BRT)*

</div>

---

## :information_source: Sobre o Projeto

Este sistema:
1. **Coleta dados** diários do Portal da Transparência de Fortaleza via API
2. **Armazena** em banco de dados SQLite (acumulativo)
3. **Visualiza** em dashboard interativo com Streamlit
4. **Agenda** execução automática todos os dias via GitHub Actions

## :chart_with_upwards_trend: Dashboard

### Funcionalidades

- **📊 Visão Geral**: Totais empenhado, liquidado e pago
- **📈 Análise Temporal**: Evolução com média móvel de 7 dias
- **🔗 Correlações**: Top favorecidos, scatter plot, matriz de correlação
- **🔍 Filtros**: Por fase, órgão e período de datas

### Dados Exibidos

- Empenhado vs Liquidado vs Pago
- Top 20 favorecidos acumulados
- Top 10 órgãos por valor pago
- Evolução diária de pagamentos
- Correlação Empenhado × Pago por órgão

---

## :rocket: Tecnologias

- **Python 3.11+**
- **Streamlit** - Dashboard interativo
- **SQLite** - Banco de dados
- **Plotly** - Gráficos interativos
- **GitHub Actions** - Automação diária
- **Hugging Face Spaces** - Hospedagem do dashboard

---

## :wrench: Instalação Local

### 1. Clonar repositório

```bash
git clone https://github.com/tiagoggl12/portal-scraper.git
cd portal-scraper
```

### 2. Instalar dependências

```bash
pip install -r requirements.txt
```

### 3. Executar scraper (coletar dados)

```bash
python3 scraper.py
```

### 4. Iniciar dashboard local

```bash
streamlit run dashboard.py
```

Acesse: http://localhost:8501

---

## :calendar: Automação

### GitHub Actions (Produção)

O scraping roda automaticamente todos os dias às **3:00 AM (BRT)** via GitHub Actions.

Ver status: https://github.com/tiagoggl12/portal-scraper/actions

### Launchd (Local - macOS)

```bash
cp com.user.portal-scraper.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.user.portal-scraper.plist
```

---

## :computer: API

Endpoint utilizado:

```
GET https://portaltransparencia-back.sepog.fortaleza.ce.gov.br/api/despesas/detalhadas/diarias/{data_inicio}/{data_fim}/{fase}
```

**Parâmetros:**
- `data_inicio`: DD-MM-YYYY
- `data_fim`: DD-MM-YYYY
- `fase`: `empenho`, `liquidacao`, ou `pagamento`

---

## :file_folder: Estrutura

```
portal-scraper/
├── scraper.py          # Script de coleta de dados
├── dashboard.py        # Dashboard Streamlit local
├── huggingface-space/  # Arquivos para deploy
│   ├── app.py         # Dashboard para Hugging Face
│   ├── README.md      # Config do Space
│   └── requirements.txt
├── .github/workflows/ # GitHub Actions
│   └── daily-scraper.yml
├── data/
│   └── despesas.db    # Banco SQLite
└── requirements.txt
```

---

## :books: Links Úteis

| Link | Descrição |
|------|-----------|
| [Dashboard](https://huggingface.co/spaces/tiagoggl12/portal-transparencia-fortaleza) | 📊 Dashboard Online |
| [GitHub Actions](https://github.com/tiagoggl12/portal-scraper/actions) | ⚙️ Status do Scraping |
| [Portal da Transparência](https://portaltransparencia.fortaleza.ce.gov.br) | 🏛️ Fonte dos Dados |

---

## :warning: Troubleshooting

| Problema | Solução |
|----------|---------|
| Banco não encontrado | Execute `python3 scraper.py` |
| Dashboard sem dados | Aguarde atualização ou execute scraper manualmente |
| GitHub Actions falhando | Verifique se a API do Portal está acessível |

---

**Desenvolvido para transparência pública das despesas de Fortaleza.**
