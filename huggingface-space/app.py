#!/usr/bin/env python3
"""
Dashboard para visualização de dados do Portal da Transparência de Fortaleza
Versão 2.0 - Responsivo com Tabs e Análises de Correlação
"""
import os
import sqlite3
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import streamlit as st
import requests

# Configuração da página
st.set_page_config(
    page_title="Portal da Transparência - Dashboard",
    page_icon=":bar_chart:",
    layout="wide",
    initial_sidebar_state="expanded"
)


# Custom CSS melhorado
st.markdown("""
<style>
    /* Header principal */
    .main-header {
        font-size: 2.2rem;
        font-weight: bold;
        color: #1a5f3f;
        text-align: center;
        padding: 1rem;
        border-bottom: 3px solid #00a195;
        margin-bottom: 1rem;
    }

    /* Metric cards com tendência */
    .metric-card {
        background: linear-gradient(135deg, #00a195 0%, #00796b 100%);
        padding: 1.2rem;
        border-radius: 12px;
        color: white;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        min-height: 100px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }

    .metric-value {
        font-size: 1.8rem;
        font-weight: bold;
        line-height: 1.2;
    }

    .metric-label {
        font-size: 0.85rem;
        opacity: 0.9;
    }

    .metric-trend {
        font-size: 0.75rem;
        margin-top: 0.5rem;
    }

    .trend-up { color: #a7f3d0; }
    .trend-down { color: #fca5a5; }
    .trend-neutral { color: #e5e7eb; }

    /* Progress bar para tabelas */
    .progress-bar {
        height: 8px;
        background: #e5e7eb;
        border-radius: 4px;
        overflow: hidden;
    }
    .progress-fill {
        height: 100%;
        background: linear-gradient(90deg, #00a195, #00796b);
        border-radius: 4px;
    }

    /* Container cards */
    .info-card {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 1rem;
        margin-bottom: 1rem;
    }

    /* Responsividade */
    @media (max-width: 768px) {
        .main-header { font-size: 1.5rem; }
        .metric-value { font-size: 1.3rem; }
    }

    /* Hide streamlit elements */
    #MainMenu { visibility: hidden; }
    .stDeployButton { display: none; }
</style>
""", unsafe_allow_html=True)


# ============================================================================
# FUNÇÕES DE DADOS
# ============================================================================

DB_PATH = "data/despesas.db"
DB_URL = "https://raw.githubusercontent.com/tiagoggl12/portal-scraper/main/data/despesas.db"

def get_db_connection():
    """Cria conexão com o banco de dados"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_database():
    """Garante que o banco de dados existe"""
    if not os.path.exists(DB_PATH):
        os.makedirs("data", exist_ok=True)

        # Try to download from GitHub
        try:
            response = requests.get(DB_URL, timeout=30)
            if response.status_code == 200:
                with open(DB_PATH, 'wb') as f:
                    f.write(response.content)
                st.success("Banco de dados atualizado!")
            else:
                st.error("Banco de dados não encontrado. Aguardando atualização...")
                return False
        except Exception as e:
            st.error(f"Erro ao baixar dados: {e}")
            return False
    return True


@st.cache_data(ttl=300)
def carregar_dados(filtro_fase: list = None, filtro_orgao: list = None,
                   data_inicio: str = None, data_fim: str = None):
    """Carrega dados do banco com filtros aplicados"""
    if not os.path.exists(DB_PATH):
        return pd.DataFrame()

    conn = get_db_connection()

    query = "SELECT * FROM despesas WHERE 1=1"
    params = []

    if filtro_fase:
        placeholders = ','.join(['?' for _ in filtro_fase])
        query += f" AND fase IN ({placeholders})"
        params.extend(filtro_fase)

    if filtro_orgao:
        placeholders = ','.join(['?' for _ in filtro_orgao])
        query += f" AND orgao IN ({placeholders})"
        params.extend(filtro_orgao)

    if data_inicio:
        query += " AND data_pagamento >= ?"
        params.append(data_inicio)

    if data_fim:
        query += " AND data_pagamento <= ?"
        params.append(data_fim)

    query += " ORDER BY data_pagamento DESC"

    try:
        df = pd.read_sql_query(query, conn, params=params)
    except:
        df = pd.DataFrame()
    finally:
        conn.close()

    return df


@st.cache_data(ttl=300)
def get_estatisticas_gerais():
    """Retorna estatísticas gerais do banco"""
    if not os.path.exists(DB_PATH):
        return pd.DataFrame(), None, []

    conn = get_db_connection()

    try:
        stats_fase = pd.read_sql_query("""
            SELECT fase,
                   SUM(valor_empenhado) as total_empenhado,
                   SUM(valor_liquidado) as total_liquidado,
                   SUM(valor_pago) as total_pago,
                   COUNT(DISTINCT data_pagamento) as dias_com_dados,
                   COUNT(*) as num_registros
            FROM despesas
            GROUP BY fase
        """, conn)

        periodo = pd.read_sql_query("""
            SELECT
                MIN(data_pagamento) as data_min,
                MAX(data_pagamento) as data_max,
                COUNT(DISTINCT data_pagamento) as total_dias
            FROM despesas
            WHERE data_pagamento IS NOT NULL
        """, conn)

        orgaos = pd.read_sql_query("""
            SELECT DISTINCT orgao
            FROM despesas
            ORDER BY orgao
        """, conn)

        return stats_fase, periodo.iloc[0] if not periodo.empty else None, orgaos['orgao'].tolist()
    except:
        return pd.DataFrame(), None, []
    finally:
        conn.close()


def calcular_tendencia(df: pd.DataFrame, coluna_valor: str, dias: int = 7) -> str:
    """Calcula tendência baseada na média dos últimos N dias"""
    if df.empty or coluna_valor not in df.columns:
        return "→"

    df_data = df[[coluna_valor]].copy()
    recentes = df_data.head(dias)[coluna_valor].sum()
    anteriores = df_data.tail(dias)[coluna_valor].sum() if len(df_data) > dias else 0

    if anteriores == 0:
        return "→"

    variacao = ((recentes - anteriores) / anteriores) * 100

    if variacao > 5:
        return f"↑ {abs(variacao):.1f}%"
    elif variacao < -5:
        return f"↓ {abs(variacao):.1f}%"
    else:
        return "→"


def formatar_moeda(valor):
    """Formata valor para moeda brasileira"""
    if pd.isna(valor) or valor == 0:
        return "R$ 0,00"
    return f"R$ {valor:,.2f}"


# ============================================================================
# COMPONENTES DE UI
# ============================================================================

def kpi_card(label: str, valor: str, trend: str = "→", delta: str = ""):
    """Renderiza um card de KPI com tendência"""
    trend_class = "trend-up" if "↑" in trend else "trend-down" if "↓" in trend else "trend-neutral"

    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{valor}</div>
        <div class="metric-label">{label}</div>
        <div class="metric-trend {trend_class}">{trend} {delta}</div>
    </div>
    """, unsafe_allow_html=True)


def top_favorecidos_table(df: pd.DataFrame, top_n: int = 20):
    """Cria tabela de top favorecidos com barras de progresso"""
    if df.empty:
        st.warning("Sem dados para exibir")
        return

    df_fav = df[df['favorecido'].notna()].groupby('favorecido')['valor_pago'].sum().reset_index()
    df_fav = df_fav.sort_values('valor_pago', ascending=False).head(top_n)

    max_valor = df_fav['valor_pago'].max()

    for idx, row in df_fav.iterrows():
        col1, col2 = st.columns([3, 1])
        with col1:
            st.write(f"**{row['favorecido'][:40]}**" if len(row['favorecido']) > 40 else f"**{row['favorecido']}**")
        with col2:
            st.markdown(f"`{formatar_moeda(row['valor_pago'])}`")
            st.markdown(f"""
            <div class="progress-bar">
                <div class="progress-fill" style="width: {(row['valor_pago']/max_valor*100):.1f}%"></div>
            </div>
            """, unsafe_allow_html=True)
        st.markdown("---")


# ============================================================================
# SIDEBAR E FILTROS
# ============================================================================

def render_sidebar(periodo, lista_orgaos, stats_fase):
    """Renderiza a sidebar com filtros"""

    st.sidebar.header(":gear: Filtros")

    # Inicializar session_state
    if 'filtros_aplicados' not in st.session_state:
        st.session_state.filtros_aplicados = False

    # Filtro de fase
    fase_disponivel = stats_fase['fase'].tolist() if not stats_fase.empty else ['pagamento']
    filtro_fase = st.sidebar.multiselect(
        "Fase da Despesa",
        options=['empenho', 'liquidacao', 'pagamento'],
        default=fase_disponivel,
        key="filtro_fase"
    )

    # Filtro de órgão (com busca)
    st.sidebar.markdown("**Órgão**")
    busca_orgao = st.sidebar.text_input("🔍 Buscar órgão...", "")

    if busca_orgao:
        orgaos_filtrados = [o for o in lista_orgaos if busca_orgao.upper() in o.upper()]
    else:
        orgaos_filtrados = lista_orgaos

    filtro_orgao = st.sidebar.multiselect(
        "Selecione órgãos",
        options=orgaos_filtrados,
        default=[],
        key="filtro_orgao"
    )

    # Filtro de data
    if periodo is not None and periodo['data_min']:
        data_min = datetime.strptime(periodo['data_min'], '%Y-%m-%d').date()
        data_max_calc = datetime.strptime(periodo['data_max'], '%Y-%m-%d').date()
    else:
        data_min = datetime.now() - timedelta(days=30)
        data_max_calc = datetime.now().date()

    col1, col2 = st.sidebar.columns(2)
    with col1:
        data_inicio = st.date_input("Data Início", data_min, key="data_inicio")
    with col2:
        data_fim = st.date_input("Data Fim", data_max_calc, key="data_fim")

    # Botões de ação
    col_a, col_b = st.sidebar.columns(2)
    with col_a:
        if st.button(":white_check_mark: Aplicar", use_container_width=True):
            st.session_state.filtros_aplicados = True
            st.rerun()
    with col_b:
        if st.button(":rotating_button: Limpar", use_container_width=True):
            st.session_state.filtros_aplicados = False
            for key in list(st.session_state.keys()):
                if key.startswith("filtro_"):
                    del st.session_state[key]
            st.rerun()

    return filtro_fase, filtro_orgao, data_inicio, data_fim


# ============================================================================
# ABA VISÃO GERAL
# ============================================================================

def tab_visao_geral(df: pd.DataFrame, stats_fase: pd.DataFrame):
    """Tab 1: Visão Geral"""
    st.header(":chart_with_upwards_trend: Visão Geral")

    # KPIs responsivos
    kpi_cols = st.columns(4)

    total_empenhado = df['valor_empenhado'].sum()
    total_liquidado = df['valor_liquidado'].sum()
    total_pago = df['valor_pago'].sum()
    num_registros = len(df)

    with kpi_cols[0]:
        kpi_card("Empenhado", formatar_moeda(total_empenhado))
    with kpi_cols[1]:
        kpi_card("Liquidado", formatar_moeda(total_liquidado))
    with kpi_cols[2]:
        kpi_card("Pago", formatar_moeda(total_pago))
    with kpi_cols[3]:
        kpi_card("Registros", f"{num_registros:,}")

    st.markdown("---")

    # Gráficos principais
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader(":calendar: Evolução Diária de Pagamentos")

        df_dia = df[df['data_pagamento'].notna()].groupby('data_pagamento')['valor_pago'].sum().reset_index()
        df_dia = df_dia.sort_values('data_pagamento')
        df_dia = df_dia.reset_index(drop=True)

        if not df_dia.empty:
            fig_linha = go.Figure()

            # Linha principal
            fig_linha.add_trace(go.Scatter(
                x=df_dia['data_pagamento'],
                y=df_dia['valor_pago'],
                mode='lines+markers',
                name='Valor Pago',
                line=dict(color='#00a195', width=3),
                marker=dict(size=8, color='#00a195')
            ))

            # Área preenchida
            fig_linha.add_trace(go.Scatter(
                x=df_dia['data_pagamento'],
                y=df_dia['valor_pago'],
                mode='lines',
                name='',
                showlegend=False,
                line=dict(width=0),
                fill='tozeroy',
                fillcolor='rgba(0, 161, 149, 0.1)'
            ))

            fig_linha.update_layout(
                xaxis_title="Data",
                yaxis_title="Valor (R$)",
                hovermode='x unified',
                margin=dict(l=0, r=0, t=20, b=0),
                height=350,
                template='plotly_white'
            )

            st.plotly_chart(fig_linha, use_container_width=True)
        else:
            st.warning("Sem dados de pagamento para exibir")

    with col_right:
        st.subheader(":building: Top 10 Órgãos por Valor Pago")

        df_orgao = df.groupby('orgao')['valor_pago'].sum().reset_index()
        df_orgao = df_orgao.sort_values('valor_pago', ascending=False).head(10)

        if not df_orgao.empty:
            fig_barra = px.bar(
                df_orgao,
                x='valor_pago',
                y='orgao',
                orientation='h',
                labels={'valor_pago': 'Valor Pago (R$)', 'orgao': 'Órgão'},
                color='valor_pago',
                color_continuous_scale=['#e0f2f1', '#00a195'],
                height=350
            )
            fig_barra.update_layout(
                yaxis={'categoryorder': 'total ascending'},
                xaxis_title="",
                yaxis_title="",
                margin=dict(l=0, r=0, t=0, b=0),
                showlegend=False
            )
            st.plotly_chart(fig_barra, use_container_width=True)
        else:
            st.warning("Sem dados para exibir")


# ============================================================================
# ABA ANÁLISE TEMPORAL
# ============================================================================

def tab_analise_temporal(df: pd.DataFrame):
    """Tab 2: Análise Temporal"""
    st.header(":chart: Análise Temporal")

    if df.empty:
        st.warning("Sem dados para análise temporal")
        return

    # Preparar dados temporais
    df_temp = df[df['data_pagamento'].notna()].copy()

    if df_temp.empty:
        st.warning("Sem dados de pagamento para análise temporal")
        return

    df_dia = df_temp.groupby('data_pagamento').agg({
        'valor_empenhado': 'sum',
        'valor_liquidado': 'sum',
        'valor_pago': 'sum',
        'favorecido': 'count'
    }).reset_index()
    df_dia = df_dia.sort_values('data_pagamento')

    # Adicionar média móvel de 7 dias
    df_dia['media_movel_7d'] = df_dia['valor_pago'].rolling(window=7, min_periods=1).mean()

    # Gráfico principal com média móvel
    st.subheader(":sparkles: Evolução com Média Móvel (7 dias)")

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df_dia['data_pagamento'],
        y=df_dia['valor_pago'],
        mode='lines+markers',
        name='Valor Pago',
        line=dict(color='#00a195', width=2),
        marker=dict(size=6)
    ))

    fig.add_trace(go.Scatter(
        x=df_dia['data_pagamento'],
        y=df_dia['media_movel_7d'],
        mode='lines',
        name='Média Móvel 7d',
        line=dict(color='#ff6b6b', width=2, dash='dash')
    ))

    fig.update_layout(
        xaxis_title="Data",
        yaxis_title="Valor (R$)",
        hovermode='x unified',
        template='plotly_white',
        height=400,
        legend=dict(orientation="h", yanchor="bottom", xanchor="center")
    )

    st.plotly_chart(fig, use_container_width=True)

    # Estatísticas por período
    col1, col2, col3 = st.columns(3)

    df_dia['data_pagamento'] = pd.to_datetime(df_dia['data_pagamento'])
    df_dia['dia_semana'] = df_dia['data_pagamento'].dt.day_name()

    with col1:
        st.metric("**Média Diária**", formatar_moeda(df_dia['valor_pago'].mean()))

    with col2:
        pico = df_dia.loc[df_dia['valor_pago'].idxmax()]
        st.metric("**Pico (Data)**", pico['data_pagamento'].strftime('%d/%m'),
                 formatar_moeda(pico['valor_pago']))

    with col3:
        st.metric("**Total Período**", formatar_moeda(df_dia['valor_pago'].sum()),
                 f"{len(df_dia)} dias")

    # Tabela detalhada
    with st.expander(":table: Ver Tabela Completa", expanded=False):
        df_display = df_dia[['data_pagamento', 'valor_pago', 'valor_empenhado',
                               'valor_liquidado', 'favorecido']].copy()
        df_display.columns = ['Data', 'Pago', 'Empenhado', 'Liquidado', 'Transações']
        df_display['Data'] = pd.to_datetime(df_display['Data']).dt.strftime('%d/%m/%Y')
        for col in ['Pago', 'Empenhado', 'Liquidado']:
            df_display[col] = df_display[col].apply(lambda x: f"R$ {x:,.2f}")
        st.dataframe(df_display, use_container_width=True, hide_index=True)


# ============================================================================
# ABA CORRELAÇÕES
# ============================================================================

def tab_correlacoes(df: pd.DataFrame):
    """Tab 3: Correlações e Análises Avançadas"""
    st.header(":link: Correlações e Análises Avançadas")

    if df.empty:
        st.warning("Sem dados para análise de correlação")
        return

    # Sub-tabs
    subtab1, subtab2, subtab3 = st.tabs(["🏆 Top Favorecidos", "📊 Empenhado x Pago", "🌡️ Matriz de Correlação"])

    with subtab1:
        st.subheader("Top 20 Favorecidos Acumulados")
        top_favorecidos_table(df, top_n=20)

    with subtab2:
        st.subheader("Scatter Plot: Empenhado vs Pago (por Órgão)")

        df_orgao = df.groupby('orgao')[['valor_empenhado', 'valor_pago']].sum().reset_index()

        if not df_orgao.empty:
            fig_scatter = px.scatter(
                df_orgao,
                x='valor_empenhado',
                y='valor_pago',
                color='orgao',
                size='valor_pago',
                hover_data=['orgao'],
                labels={
                    'valor_empenhado': 'Valor Empenhado (R$)',
                    'valor_pago': 'Valor Pago (R$)',
                    'orgao': 'Órgão'
                },
                color_discrete_sequence=px.colors.qualitative.Safe,
                height=500
            )

            # Adicionar linha diagonal (y=x)
            max_val = max(df_orgao['valor_empenhado'].max(), df_orgao['valor_pago'].max())
            fig_scatter.add_shape(
                type='line',
                line=dict(color='gray', dash='dot'),
                x0=0, y0=0, x1=max_val, y1=max_val
            )

            fig_scatter.update_layout(
                xaxis_title="Valor Empenhado (R$)",
                yaxis_title="Valor Pago (R$)",
                template='plotly_white'
            )

            st.plotly_chart(fig_scatter, use_container_width=True)

            with st.expander("Interpretação"):
                st.info("""
                - **Pontos acima da linha**: Pago maior que empenhado (pagamentos de períodos anteriores)
                - **Pontos na linha**: Pago ≈ Empenhado (pagamento rápido)
                - **Tamanho do ponto**: Valor total pago
                """)

    with subtab3:
        st.subheader("Matriz de Correlação")

        # Selecionar variáveis numéricas
        vars_numericas = ['valor_empenhado', 'valor_liquidado', 'valor_pago', 'valor_anulado']

        # Calcular correlação por órgão
        correlations = []
        for orgao in df['orgao'].unique():
            df_org = df[df['orgao'] == orgao]
            if len(df_org) > 1:
                corr = df_org[vars_numericas].corr().loc['valor_pago', 'valor_empenhado']
                correlations.append({
                    'orgao': orgao[:30],
                    'correlacao': corr if not pd.isna(corr) else 0,
                    'total_pago': df_org['valor_pago'].sum()
                })

        df_corr = pd.DataFrame(correlations).sort_values('correlacao', ascending=False)

        if not df_corr.empty:
            col1, col2 = st.columns([2, 1])

            with col1:
                # Heatmap de correlação por órgão
                top_corr = df_corr.head(15)

                fig_heatmap = px.bar(
                    top_corr,
                    x='correlacao',
                    y='orgao',
                    orientation='h',
                    color='correlacao',
                    color_continuous_scale=['#f87171', '#fbbf24', '#34d399'],
                    labels={'correlacao': 'Correlação', 'orgao': 'Órgão'},
                    height=400
                )
                fig_heatmap.update_layout(
                    xaxis_title="Correlação (Empenho × Pago)",
                    yaxis_title="",
                    showlegend=False,
                    margin=dict(l=0, r=0, t=0, b=0)
                )
                st.plotly_chart(fig_heatmap, use_container_width=True)

            with col2:
                # Estatísticas
                st.markdown("**Estatísticas de Correlação**")
                st.write(f"**Média:** {df_corr['correlacao'].mean():.3f}")
                st.write(f"**Mediana:** {df_corr['correlacao'].median():.3f}")

                with st.expander("Ver dados brutos"):
                    st.dataframe(df_corr, use_container_width=True, hide_index=True)


# ============================================================================
# FUNÇÃO PRINCIPAL
# ============================================================================

def main():
    # Header
    st.markdown('<h1 class="main-header">:cityscape: Portal da Transparência de Fortaleza</h1>', unsafe_allow_html=True)

    # Garantir banco de dados
    if not ensure_database():
        st.warning("Banco de dados em carregamento. Tente novamente em alguns instantes.")
        return

    # Carregar dados
    stats_fase, periodo, lista_orgaos = get_estatisticas_gerais()

    if periodo is None or periodo['data_min'] is None:
        st.warning("Nenhum dado disponível. Os dados são atualizados diariamente.")
        return

    # Renderizar sidebar e obter filtros
    filtro_fase, filtro_orgao, data_inicio, data_fim = render_sidebar(periodo, lista_orgaos, stats_fase)

    # Carregar dados com filtros
    df = carregar_dados(
        filtro_fase=filtro_fase if filtro_fase else None,
        filtro_orgao=filtro_orgao if filtro_orgao else None,
        data_inicio=str(data_inicio),
        data_fim=str(data_fim)
    )

    if df.empty:
        st.warning("Nenhum dado encontrado com os filtros selecionados.")
        return

    # Mostrar período dos dados
    cols_info = st.columns([3, 1, 1])
    with cols_info[0]:
        st.caption(f"Período: **{periodo['data_min']}** a **{periodo['data_max']}**")
    with cols_info[1]:
        st.caption(f"{periodo['total_dias']} dias")
    with cols_info[2]:
        st.caption(f"{len(df):,} registros")

    # Tabs principais
    tab1, tab2, tab3 = st.tabs(["📊 Visão Geral", "📈 Análise Temporal", "🔗 Correlações"])

    with tab1:
        tab_visao_geral(df, stats_fase)

    with tab2:
        tab_analise_temporal(df)

    with tab3:
        tab_correlacoes(df)


if __name__ == "__main__":
    main()
