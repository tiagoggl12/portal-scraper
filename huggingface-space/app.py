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
import networkx as nx
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


def formatar_data_brasil(data_str):
    """Formata data de YYYY-MM-DD para DD/MM/YYYY"""
    if pd.isna(data_str) or data_str == '':
        return '-'
    try:
        dt = pd.to_datetime(data_str)
        return dt.strftime('%d/%m/%Y')
    except:
        return str(data_str)


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

        # Adicionar data formatada para exibição
        df_dia['data_formatada'] = pd.to_datetime(df_dia['data_pagamento']).dt.strftime('%d/%m/%Y')

        if not df_dia.empty:
            fig_linha = go.Figure()

            # Linha principal
            fig_linha.add_trace(go.Scatter(
                x=df_dia['data_pagamento'],
                y=df_dia['valor_pago'],
                mode='lines+markers',
                name='Valor Pago',
                line=dict(color='#00a195', width=3),
                marker=dict(size=8, color='#00a195'),
                text=df_dia['data_formatada']
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
                template='plotly_white',
                xaxis=dict(
                    tickmode='array',
                    tickvals=df_dia['data_pagamento'],
                    ticktext=df_dia['data_formatada']
                )
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

    # Adicionar data formatada para exibição
    df_dia['data_formatada'] = pd.to_datetime(df_dia['data_pagamento']).dt.strftime('%d/%m/%Y')

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
        legend=dict(orientation="h", yanchor="bottom", xanchor="center"),
        xaxis=dict(
            tickmode='array',
            tickvals=df_dia['data_pagamento'],
            ticktext=df_dia['data_formatada']
        )
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
# GRAFO DE CORRELAÇÕES
# ============================================================================

def criar_grafo_correlacoes(df: pd.DataFrame, min_correlacao: float = 0.3, top_n_orgaos: int = 15):
    """
    Cria um grafo de correlações usando Plotly.

    Args:
        df: DataFrame com os dados
        min_correlacao: Correlação mínima para exibir conexão
        top_n_orgaos: Número de órgãos a incluir

    Returns:
        Figure do Plotly com o grafo
    """
    if df.empty:
        return go.Figure()

    # Variáveis numéricas base
    vars_numericas = ['valor_empenhado', 'valor_liquidado', 'valor_pago', 'valor_anulado']

    # 1. Calcular matriz de correlação geral (variáveis numéricas)
    df_corr_geral = df[vars_numericas].corr()

    # 2. Calcular correlações por órgão
    top_orgaos = df.groupby('orgao')['valor_pago'].sum().nlargest(top_n_orgaos).index.tolist()

    # Criar grafo NetworkX
    G = nx.Graph()

    # Adicionar nós das variáveis numéricas
    labels_vars = {
        'valor_empenhado': 'Empenhado',
        'valor_liquidado': 'Liquidado',
        'valor_pago': 'Pago',
        'valor_anulado': 'Anulado'
    }

    for var in vars_numericas:
        G.add_node(var, label=labels_vars[var], type='variavel', size=30)

    # Adicionar nós dos órgãos
    for i, orgao in enumerate(top_orgaos):
        nome_curto = orgao[:25] + '...' if len(orgao) > 25 else orgao
        G.add_node(f"org_{i}", label=nome_curto, type='orgao', nome_orgao=orgao, size=20)

    # Adicionar arestas entre variáveis (correlação geral)
    for i, var1 in enumerate(vars_numericas):
        for j, var2 in enumerate(vars_numericas):
            if i < j:
                corr = df_corr_geral.loc[var1, var2]
                if abs(corr) >= min_correlacao:
                    G.add_edge(var1, var2, weight=abs(corr), correlation=corr, tipo='variavel')

    # Adicionar arestas entre órgãos baseado em correlação de padrões de pagamento
    for i, orgao1 in enumerate(top_orgaos):
        for j, orgao2 in enumerate(top_orgaos):
            if i < j:
                # Calcular correlação entre os padrões de pagamento dos dois órgãos
                df_org1 = df[df['orgao'] == orgao1][['data_pagamento', 'valor_pago']].dropna()
                df_org2 = df[df['orgao'] == orgao2][['data_pagamento', 'valor_pago']].dropna()

                if len(df_org1) > 2 and len(df_org2) > 2:
                    # Merge por data para calcular correlação
                    df_merged = pd.merge(
                        df_org1.groupby('data_pagamento')['valor_pago'].sum(),
                        df_org2.groupby('data_pagamento')['valor_pago'].sum(),
                        on='data_pagamento', suffixes=('_1', '_2'), how='inner'
                    )

                    if len(df_merged) > 2:
                        corr = df_merged['valor_pago_1'].corr(df_merged['valor_pago_2'])
                        if not pd.isna(corr) and abs(corr) >= min_correlacao:
                            G.add_edge(
                                f"org_{i}", f"org_{j}",
                                weight=abs(corr),
                                correlation=corr,
                                tipo='orgao'
                            )

    # Layout do grafo usando spring layout
    pos = nx.spring_layout(G, k=2, iterations=50, seed=42)

    # Extrair informações para Plotly
    node_x = []
    node_y = []
    node_text = []
    node_colors = []
    node_sizes = []

    color_map = {
        'variavel': '#00a195',
        'orgao': '#ff6b6b'
    }

    for node, data in G.nodes(data=True):
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
        node_text.append(data.get('label', node))
        node_colors.append(color_map.get(data.get('type', 'variavel'), '#00a195'))
        node_sizes.append(data.get('size', 20))

    # Arestas
    edge_x = []
    edge_y = []
    edge_colors = []
    edge_widths = []

    for edge in G.edges(data=True):
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])

        corr = edge[2].get('correlation', 0)
        # Verde para positivo, vermelho para negativo
        if corr > 0:
            edge_colors.append('rgba(0, 161, 149, 0.6)')
        else:
            edge_colors.append('rgba(255, 107, 107, 0.6)')

        # Largura baseada na força da correlação
        edge_widths.append(abs(corr) * 5)

    # Criar figura Plotly
    fig = go.Figure()

    # Adicionar arestas
    for i in range(0, len(edge_x), 3):
        fig.add_trace(go.Scatter(
            x=edge_x[i:i+3],
            y=edge_y[i:i+3],
            mode='lines',
            line=dict(
                color=edge_colors[i//3] if i//3 < len(edge_colors) else 'rgba(150,150,150,0.3)',
                width=edge_widths[i//3] if i//3 < len(edge_widths) else 1
            ),
            hoverinfo='none',
            showlegend=False
        ))

    # Adicionar nós
    fig.add_trace(go.Scatter(
        x=node_x,
        y=node_y,
        mode='markers+text',
        marker=dict(
            size=node_sizes,
            color=node_colors,
            line=dict(color='white', width=2)
        ),
        text=node_text,
        textposition='middle center',
        textfont=dict(size=10, color='white'),
        hovertemplate='<b>%{text}</b><extra></extra>',
        showlegend=False
    ))

    # Adicionar anotações das correlações nas arestas
    for edge in G.edges(data=True):
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        corr = edge[2].get('correlation', 0)

        if abs(corr) >= min_correlacao:
            x_mid = (x0 + x1) / 2
            y_mid = (y0 + y1) / 2

            fig.add_annotation(
                x=x_mid,
                y=y_mid,
                text=f"{corr:.2f}",
                showarrow=False,
                font=dict(size=8, color='white'),
                bgcolor='rgba(0,0,0,0.7)',
                bordercolor=corr > 0 and '#34d399' or '#f87171',
                borderwidth=1,
                borderpad=2
            )

    fig.update_layout(
        title=dict(
            text='Grafo de Correlações',
            x=0.5,
            xanchor='center',
            font=dict(size=18, color='#1a5f3f')
        ),
        showlegend=False,
        hovermode='closest',
        margin=dict(b=20, l=5, r=5, t=40),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        plot_bgcolor='white',
        paper_bgcolor='white',
        height=600
    )

    # Adicionar legenda
    fig.add_annotation(
        x=0.02, y=0.98,
        xref='paper', yref='paper',
        text='<b>Legenda:</b><br>' +
             '<span style="color:#00a195">■ Variáveis</span><br>' +
             '<span style="color:#ff6b6b">■ Órgãos</span><br>' +
             '<span style="color:#34d399">─ Corr. Positiva</span><br>' +
             '<span style="color:#f87171">─ Corr. Negativa</span>',
        showarrow=False,
        font=dict(size=11),
        bgcolor='rgba(255,255,255,0.9)',
        bordercolor='#e2e8f0',
        borderwidth=1,
        borderpad=10,
        align='left'
    )

    return fig


def criar_grafo_outras_correlacoes(df: pd.DataFrame, tipo: str = 'variaveis'):
    """
    Cria gráficos de correlação alternativos.

    Args:
        df: DataFrame com os dados
        tipo: Tipo de grafo ('variaveis', 'orgaos')

    Returns:
        Figure do Plotly
    """
    if df.empty:
        return go.Figure()

    if tipo == 'variaveis':
        # Matriz de correlação das variáveis numéricas
        vars_numericas = ['valor_empenhado', 'valor_liquidado', 'valor_pago', 'valor_anulado']
        df_corr = df[vars_numericas].corr()

        labels = ['Empenhado', 'Liquidado', 'Pago', 'Anulado']

        fig = go.Figure(data=go.Heatmap(
            z=df_corr.values,
            x=labels,
            y=labels,
            colorscale='RdYlGn',
            zmid=0,
            text=np.round(df_corr.values, 2),
            texttemplate='%{text}',
            textfont={"size": 12},
            colorbar=dict(title="Correlação")
        ))

        fig.update_layout(
            title='Matriz de Correlação das Variáveis',
            xaxis_title='',
            yaxis_title='',
            height=500
        )

        return fig

    elif tipo == 'sankey':
        # Sankey diagram mostrando fluxo: Empenhado -> Liquidado -> Pago por órgão
        top_orgaos = df.groupby('orgao')['valor_empenhado'].sum().nlargest(8).index.tolist()

        df_filtrado = df[df['orgao'].isin(top_orgaos)]

        # Preparar dados para Sankey
        empenhado_por_orgao = df_filtrado.groupby('orgao')['valor_empenhado'].sum()
        liquidado_por_orgao = df_filtrado.groupby('orgao')['valor_liquidado'].sum()
        pago_por_orgao = df_filtrado.groupby('orgao')['valor_pago'].sum()

        # Nós
        nodes = ['Empenhado'] + list(top_orgaos) + ['Pago']
        node_dict = {node: i for i, node in enumerate(nodes)}

        # Links
        sources = []
        targets = []
        values = []
        labels = []

        # Empenhado -> Órgãos
        for orgao in top_orgaos:
            val = empenhado_por_orgao[orgao]
            if val > 0:
                sources.append(node_dict['Empenhado'])
                targets.append(node_dict[orgao])
                values.append(val)
                labels.append(orgao[:20])

        # Órgãos -> Pago
        for orgao in top_orgaos:
            val = pago_por_orgao[orgao]
            if val > 0:
                sources.append(node_dict[orgao])
                targets.append(node_dict['Pago'])
                values.append(val)
                labels.append(orgao[:20])

        # Cores para órgãos
        colors_orgaos = [f'rgba(0, {100 + i*15}, 149, 0.5)' for i in range(len(top_orgaos))]

        fig = go.Figure(data=[go.Sankey(
            node=dict(
                pad=15,
                thickness=20,
                line=dict(color='white', width=0.5),
                label=nodes,
                color=['#00a195'] + colors_orgaos + ['#00a195']
            ),
            link=dict(
                source=sources,
                target=targets,
                value=values,
                color=colors_orgaos * 2
            )
        )])

        fig.update_layout(
            title='Fluxo Financeiro: Empenhado → Pago (Top 8 Órgãos)',
            height=600
        )

        return fig


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
    subtab1, subtab2, subtab3, subtab4 = st.tabs([
        "🕸️ Grafo de Correlações",
        "🏆 Top Favorecidos",
        "📊 Empenhado x Pago",
        "🌡️ Matriz de Correlação"
    ])

    with subtab1:
        st.subheader("Visualização em Grafo")

        col1, col2, col3 = st.columns(3)
        with col1:
            min_corr = st.slider(
                "Correlação Mínima",
                min_value=0.0,
                max_value=0.9,
                value=0.3,
                step=0.1,
                help="Correlação mínima para exibir conexão entre nós"
            )
        with col2:
            top_n = st.selectbox(
                "Top Órgãos",
                options=[5, 10, 15, 20, 25],
                index=2,
                help="Número de órgãos a incluir no grafo"
            )
        with col3:
            tipo_grafo = st.selectbox(
                "Tipo de Visualização",
                options=["Grafo de Rede", "Matriz de Calor", "Diagrama Sankey"],
                index=0
            )

        if tipo_grafo == "Grafo de Rede":
            fig = criar_grafo_correlacoes(df, min_correlacao=min_corr, top_n_orgaos=top_n)
            st.plotly_chart(fig, use_container_width=True)

            with st.expander("ℹ️ Interpretação do Grafo"):
                st.info("""
                **O que o grafo mostra:**

                - **Nós verdes (Variáveis)**: Empenhado, Liquidado, Pago, Anulado
                - **Nós vermelhos (Órgãos)**: Top órgãos por valor pago

                **Conexões (Arestas):**
                - **Linhas verdes**: Correlação positiva (variam juntas)
                - **Linhas vermelhas**: Correlação negativa (variam em oposição)
                - **Espessura**: Força da correlação (mais espesso = mais forte)
                - **Números nas arestas**: Valor da correlação (-1 a 1)

                **Exemplos de interpretação:**
                - Correlação próxima de 1: quando uma sobe, a outra também sobe
                - Correlação próxima de -1: quando uma sobe, a outra desce
                - Correlação próxima de 0: não há relação linear
                """)

        elif tipo_grafo == "Matriz de Calor":
            fig = criar_grafo_outras_correlacoes(df, tipo='variaveis')
            st.plotly_chart(fig, use_container_width=True)

        elif tipo_grafo == "Diagrama Sankey":
            fig = criar_grafo_outras_correlacoes(df, tipo='sankey')
            st.plotly_chart(fig, use_container_width=True)

            with st.expander("ℹ️ Interpretação do Sankey"):
                st.info("""
                **O que o diagrama mostra:**

                Fluxo financeiro do valor **Empenhado** → **Pago** através dos principais órgãos.

                - **Largura das faixas**: Valor financeiro
                - **Cores**: Diferentes órgãos

                Útil para visualizar quais órgãos têm maior volume de empenhos
                e quanto efetivamente foi pago.
                """)

    with subtab2:
        st.subheader("Top 20 Favorecidos Acumulados")
        top_favorecidos_table(df, top_n=20)

    with subtab3:
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

    with subtab4:
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
# ABA DADOS DETALHADOS
# ============================================================================

def tab_dados_detalhados(df: pd.DataFrame):
    """Tab 4: Dados Detalhados com busca e filtros"""
    st.header(":page_facing_up: Dados Detalhados")

    if df.empty:
        st.warning("Sem dados para exibir")
        return

    # Converter colunas de data
    for col in ['data_pagamento', 'data_empenho', 'data_liquidacao']:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')

    # Busca textual
    st.subheader(":mag: Buscar")
    busca = st.text_input("Digite para buscar (favorecido, órgão, objeto)...", "")

    if busca:
        filtro = df['favorecido'].str.contains(busca, case=False, na=False) | \
                df['orgao'].str.contains(busca, case=False, na=False) | \
                df['objeto'].str.contains(busca, case=False, na=False)
        df = df[filtro]
        st.info(f":mag: {len(df)} registros encontrados")

    # Colunas para exibir
    colunas_principais = [
        'data_pagamento', 'fase', 'favorecido', 'orgao',
        'valor_empenhado', 'valor_liquidado', 'valor_pago', 'objeto'
    ]

    # Formatardata para exibição
    df_display = df[colunas_principais].copy()

    # Aplicar formatação
    df_display['data_pagamento'] = df_display['data_pagamento'].dt.strftime('%d/%m/%Y')
    df_display['valor_empenhado'] = df_display['valor_empenhado'].apply(lambda x: f"R$ {x:,.2f}" if pd.notna(x) else "-")
    df_display['valor_liquidado'] = df_display['valor_liquidado'].apply(lambda x: f"R$ {x:,.2f}" if pd.notna(x) else "-")
    df_display['valor_pago'] = df_display['valor_pago'].apply(lambda x: f"R$ {x:,.2f}" if pd.notna(x) else "-")

    # Renomear colunas
    df_display.columns = [
        'Data Pagto', 'Fase', 'Favorecido', 'Órgão',
        'Empenhado', 'Liquidado', 'Pago', 'Objeto'
    ]

    # Limitar objeto para exibição
    df_display['Objeto'] = df_display['Objeto'].str[:100] + '...'

    st.caption(f":heavy_check_mark: Mostrando {len(df_display)} registros")

    # Dataframe com busca por coluna
    st.dataframe(
        df_display,
        use_container_width=True,
        hide_index=True,
        height=500
    )

    # Exportar dados
    st.subheader(":download: Exportar Dados")

    col1, col2, col3 = st.columns(3)

    with col1:
        # Exportar como CSV
        csv_data = df_display.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📄 Baixar CSV",
            data=csv_data,
            file_name=f"despesas_detalhadas_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )

    with col2:
        # Contar por fase
        st.metric("Empenhos", f"{df['valor_empenhado'].sum():,.0f}")
        st.metric("Pagamentos", f"{df['valor_pago'].sum():,.0f}")

    with col3:
        st.metric("Registros", f"{len(df):,}")


# ============================================================================
# FUNÇÃO PRINCIPAL
# ============================================================================

def main():
    # Header
    st.markdown('<h1 class="main-header">:cityscape: Portal da Transparência de Fortaleza</h1>', unsafe_allow_html=True)

    # Fonte dos dados
    st.markdown("""
    <div style="text-align: center; padding: 0.5rem; margin-bottom: 1rem; background: #f0fdf4; border-radius: 8px; border: 1px solid #bbf7d0;">
        <strong>📊 Fonte dos Dados:</strong>
        <a href="https://portaltransparencia.fortaleza.ce.gov.br/#/despesas/detalhadas" target="_blank" style="color: #166534; font-weight: 600;">
            Portal da Transparência de Fortaleza
        </a> -
        <strong>Despesas Detalhadas</strong>
    </div>
    """, unsafe_allow_html=True)

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
        st.caption(f"Período: **{formatar_data_brasil(periodo['data_min'])}** a **{formatar_data_brasil(periodo['data_max'])}**")
    with cols_info[1]:
        st.caption(f"{periodo['total_dias']} dias")
    with cols_info[2]:
        st.caption(f"{len(df):,} registros")

    # Tabs principais
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Visão Geral", "📈 Análise Temporal", "🔗 Correlações", "📋 Dados Detalhados"])

    with tab1:
        tab_visao_geral(df, stats_fase)

    with tab2:
        tab_analise_temporal(df)

    with tab3:
        tab_correlacoes(df)

    with tab4:
        tab_dados_detalhados(df)


if __name__ == "__main__":
    main()
