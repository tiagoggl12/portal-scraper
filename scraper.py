#!/usr/bin/env python3
"""
Web Scraper para Portal da Transparência de Fortaleza
Baixa dados de despesas detalhadas diárias via API
"""
import os
import json
import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path
import requests
from typing import List, Dict, Optional


# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class PortalTransparenciaAPI:
    """Cliente para a API do Portal da Transparência de Fortaleza"""

    BASE_URL = "https://portaltransparencia-back.sepog.fortaleza.ce.gov.br/api"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json',
            'User-Agent': 'Mozilla/5.0 (compatible; PortalTransparenciaScraper/1.0)'
        })

    def get_despesas_detalhadas(
        self,
        data_inicio: str,
        data_fim: str,
        fase: str = "pagamento"
    ) -> List[Dict]:
        """
        Busca despesas detalhadas por período e fase

        Args:
            data_inicio: Data no formato DD-MM-YYYY
            data_fim: Data no formato DD-MM-YYYY
            fase: Fase da despesa (empenho, liquidacao, pagamento)

        Returns:
            Lista de dicionários com os dados das despesas
        """
        url = f"{self.BASE_URL}/despesas/detalhadas/diarias/{data_inicio}/{data_fim}/{fase}"

        logger.info(f"Buscando dados: {url}")

        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            dados = response.json()

            if not isinstance(dados, list):
                logger.error(f"Resposta inesperada: {type(dados)}")
                return []

            logger.info(f"Recebidos {len(dados)} registros")
            return dados

        except requests.RequestException as e:
            logger.error(f"Erro na requisição: {e}")
            return []

    def get_despesas_por_fase(
        self,
        data_inicio: str,
        data_fim: str
    ) -> Dict[str, List[Dict]]:
        """Busca despesas de todas as fases"""
        fases = ["empenho", "liquidacao", "pagamento"]
        resultados = {}

        for fase in fases:
            resultados[fase] = self.get_despesas_detalhadas(data_inicio, data_fim, fase)

        return resultados


class DatabaseManager:
    """Gerencia o banco de dados SQLite"""

    def __init__(self, db_path: str = "data/despesas.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Inicializa o banco de dados e cria tabelas"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS despesas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    api_id INTEGER UNIQUE,
                    exercicio INTEGER,
                    data_empenho TEXT,
                    data_liquidacao TEXT,
                    data_pagamento TEXT,
                    fase TEXT,
                    especie_empenho TEXT,
                    favorecido TEXT,
                    documento_favorecido TEXT,
                    orgao TEXT,
                    dotacao_orcamentaria TEXT,
                    valor_empenhado REAL,
                    valor_liquidado REAL,
                    valor_pago REAL,
                    valor_anulado REAL,
                    objeto TEXT,
                    data_coleta TEXT,
                    UNIQUE(api_id, fase)
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_data_pagamento
                ON despesas(data_pagamento)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_orgao
                ON despesas(orgao)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_fase
                ON despesas(fase)
            """)

            conn.commit()
            logger.info("Banco de dados inicializado")

    def insert_despesas(self, despesas: List[Dict], fase: str) -> int:
        """Insere despesas no banco de dados"""
        if not despesas:
            return 0

        data_coleta = datetime.now().isoformat()
        inserted = 0
        updated = 0

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            for desp in despesas:
                try:
                    # Extrair dados do JSON da API
                    api_id = desp.get('ID')
                    exercicio = desp.get('EXERCICIO')

                    data_pag = desp.get('DATAPAGAMENTO', '')
                    if data_pag:
                        data_pag = datetime.fromisoformat(data_pag).strftime('%Y-%m-%d')

                    data_liq = desp.get('DATALIQUIDACAO', '')
                    if data_liq:
                        data_liq = datetime.fromisoformat(data_liq).strftime('%Y-%m-%d')

                    data_emp = desp.get('DATAEMPENHO', '')
                    if data_emp:
                        data_emp = datetime.fromisoformat(data_emp).strftime('%Y-%m-%d')

                    cursor.execute("""
                        INSERT OR REPLACE INTO despesas
                        (api_id, exercicio, data_empenho, data_liquidacao, data_pagamento,
                         fase, especie_empenho, favorecido, documento_favorecido, orgao,
                         dotacao_orcamentaria, valor_empenhado, valor_liquidado, valor_pago,
                         valor_anulado, objeto, data_coleta)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        api_id,
                        exercicio,
                        data_emp,
                        data_liq,
                        data_pag,
                        fase,
                        desp.get('ESPECIEEMPENHO'),
                        desp.get('NOMECREDOR'),
                        desp.get('DOCUMENTOCREDOR'),
                        desp.get('DESCRICAOUO'),
                        desp.get('CODIGODOTACAO'),
                        desp.get('VALOREMPENHADO') or 0,
                        desp.get('VALORLIQUIDADO') or 0,
                        desp.get('VALORPAGO') or 0,
                        desp.get('VALORANULADO') or 0,
                        desp.get('OBJETOEMPENHO', '')[:500],  # Limita tamanho
                        data_coleta
                    ))
                    inserted += 1

                except sqlite3.IntegrityError:
                    updated += 1
                except Exception as e:
                    logger.warning(f"Erro ao inserir registro {api_id}: {e}")

            conn.commit()

        logger.info(f"Inseridos: {inserted}, Atualizados: {updated}")
        return inserted

    def get_estatisticas(self) -> Dict:
        """Retorna estatísticas agregadas do banco de dados"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Total por fase
            cursor.execute("""
                SELECT fase,
                       SUM(valor_empenhado) as total_empenhado,
                       SUM(valor_liquidado) as total_liquidado,
                       SUM(valor_pago) as total_pago,
                       COUNT(*) as num_registros
                FROM despesas
                GROUP BY fase
            """)
            por_fase = [dict(row) for row in cursor.fetchall()]

            # Total por órgão (últimos 30 dias)
            cursor.execute("""
                SELECT orgao,
                       SUM(valor_pago) as total_pago,
                       COUNT(*) as num_registros
                FROM despesas
                WHERE data_pagamento >= date('now', '-30 days')
                GROUP BY orgao
                ORDER BY total_pago DESC
                LIMIT 20
            """)
            por_orgao = [dict(row) for row in cursor.fetchall()]

            # Total por dia (últimos 30 dias)
            cursor.execute("""
                SELECT data_pagamento,
                       SUM(valor_pago) as total_pago,
                       COUNT(*) as num_registros
                FROM despesas
                WHERE data_pagamento IS NOT NULL
                  AND data_pagamento >= date('now', '-30 days')
                GROUP BY data_pagamento
                ORDER BY data_pagamento DESC
            """)
            por_dia = [dict(row) for row in cursor.fetchall()]

            # Data mais recente e mais antiga
            cursor.execute("""
                SELECT MIN(data_pagamento) as min_data,
                       MAX(data_pagamento) as max_data
                FROM despesas
                WHERE data_pagamento IS NOT NULL
            """)
            periodo = dict(cursor.fetchone() or {})

            return {
                'por_fase': por_fase,
                'por_orgao': por_orgao,
                'por_dia': por_dia,
                'periodo': periodo
            }

    def exportar_para_csv(self, output_path: str, fase: str = "pagamento"):
        """Exporta dados para CSV"""
        import csv

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT * FROM despesas
                WHERE fase = ?
                ORDER BY data_pagamento DESC
            """, (fase,))

            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()

            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(columns)
                writer.writerows(rows)

            logger.info(f"Exportados {len(rows)} registros para {output_path}")


def formatar_data(data: datetime) -> str:
    """Formata data para o formato da API (DD-MM-YYYY)"""
    return data.strftime('%d-%m-%Y')


def baixar_dados_anteriores(db: DatabaseManager, api: PortalTransparenciaAPI, dias: int = 30):
    """Baixa dados dos últimos N dias"""
    logger.info(f"Baixando dados dos últimos {dias} dias...")

    for i in range(dias):
        data = datetime.now() - timedelta(days=i+1)  # +1 para pegar ontem
        data_str = formatar_data(data)

        logger.info(f"Baixando dados de {data_str}")

        for fase in ["empenho", "liquidacao", "pagamento"]:
            despesas = api.get_despesas_detalhadas(data_str, data_str, fase)
            if despesas:
                db.insert_despesas(despesas, fase)


def baixar_dia_anterior(db: DatabaseManager, api: PortalTransparenciaAPI):
    """Baixa dados do dia anterior (uso diário)"""
    ontem = datetime.now() - timedelta(days=1)
    data_str = formatar_data(ontem)

    logger.info(f"Baixando dados de {data_str} (dia anterior)")

    total_inserido = 0
    for fase in ["empenho", "liquidacao", "pagamento"]:
        despesas = api.get_despesas_detalhadas(data_str, data_str, fase)
        if despesas:
            total_inserido += db.insert_despesas(despesas, fase)

    # Salvar JSON backup
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)

    backup_file = data_dir / f"despesas_{ontem.strftime('%Y%m%d')}.json"

    todas_fases = api.get_despesas_por_fase(data_str, data_str)
    with open(backup_file, 'w', encoding='utf-8') as f:
        json.dump(todas_fases, f, ensure_ascii=False, indent=2)

    logger.info(f"Backup salvo em {backup_file}")

    return total_inserido


def main():
    """Função principal"""
    logger.info("=" * 50)
    logger.info("Iniciando scraper do Portal da Transparência")
    logger.info("=" * 50)

    api = PortalTransparenciaAPI()
    db = DatabaseManager()

    # Baixar dados do dia anterior
    total = baixar_dia_anterior(db, api)

    # Mostrar estatísticas
    stats = db.get_estatisticas()

    logger.info("\n" + "=" * 50)
    logger.info("RESUMO")
    logger.info("=" * 50)

    for fase_data in stats['por_fase']:
        logger.info(
            f"{fase_data['fase'].upper()}: "
            f"{fase_data['num_registros']} registros, "
            f"R$ {fase_data['total_pago']:,.2f} pagos"
                if fase_data['total_pago'] else 0
        )

    logger.info(f"\nPeríodo de dados: {stats['periodo'].get('min_data')} a {stats['periodo'].get('max_data')}")
    logger.info(f"Total inserido nesta execução: {total} registros")

    return total


if __name__ == "__main__":
    main()
