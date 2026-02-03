# Instruções de Deploy - Portal da Transparência

## 📦 Repositório GitHub

✅ Criado: https://github.com/tiagoggl12/portal-scraper

### GitHub Actions (Scraping Automático)
O workflow está configurado para rodar automaticamente todos os dias às 3 AM (BRT).

Para verificar: https://github.com/tiagoggl12/portal-scraper/actions

---

## 🚀 Deploy do Dashboard (Hugging Face Spaces)

### Passo 1: Criar conta no Hugging Face
1. Acesse: https://huggingface.co/join
2. Crie sua conta gratuita

### Passo 2: Criar um Space
1. Acesse: https://huggingface.co/new-space
2. Configure:
   - **Owner**: Seu username
   - **Space name**: portal-transparencia-fortaleza
   - **License**: MIT
   - **SDK**: Streamlit
   - **Hardware**: CPU basic (free)

### Passo 3: Fazer upload dos arquivos

#### Opção A - Via interface web:
1. No seu Space, clique em "Files"
2. Upload estes arquivos da pasta `huggingface-space/`:
   - `README.md`
   - `app.py`
   - `requirements.txt`

#### Opção B - Via Git:
```bash
# Instalar o CLI do Hugging Face
pip install huggingface_hub

# Fazer login
huggingface-cli login

# Criar o espaço e fazer upload
cd huggingface-space
git init
git remote add space https://huggingface.co/spaces/SEU_USERNAME/portal-transparencia-fortaleza
git add .
git commit -m "Initial commit"
git push
```

### Passo 4: Configurar atualização dos dados
O dashboard vai baixar os dados automaticamente do GitHub.
O arquivo `data/despesas.db` será baixado do repositório a cada refresh.

---

## 📊 Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│                    GitHub Actions                            │
│  (Roda todo dia às 3 AM - baixa dados do portal)            │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              GitHub Repository (Dados)                       │
│  https://github.com/tiagoggl12/portal-scraper               │
│  - data/despesas.db (banco de dados acumulado)              │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│            Hugging Face Spaces (Dashboard)                   │
│  https://huggingface.co/spaces/SEU_USERNAME/...             │
│  - Streamlit Dashboard                                      │
│  - Baixa dados do GitHub automaticamente                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔧 Configurações Locais

### Para rodar o dashboard localmente:
```bash
cd /Users/tiago/portal-scraper
streamlit run dashboard.py
```

### Para rodar o scraper manualmente:
```bash
cd /Users/tiago/portal-scraper
python3 scraper.py
```

### Para agendar o scraping no macOS (launchd):
```bash
# Copiar o plist para o diretório de launch agents
cp com.user.portal-scraper.plist ~/Library/LaunchAgents/

# Carregar o agent
launchctl load ~/Library/LaunchAgents/com.user.portal-scraper.plist

# Verificar status
launchctl list | grep portal-scraper
```
