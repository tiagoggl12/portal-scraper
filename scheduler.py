#!/usr/bin/env python3
"""
Agendador para execução automática diária do scraper
Execute: python scheduler.py
"""
import time
import schedule
import logging
from datetime import datetime
from scraper import PortalTransparenciaAPI, DatabaseManager, baixar_dia_anterior


# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/scheduler.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def job_baixar_dados():
    """Job diário de download de dados"""
    logger.info("=" * 50)
    logger.info("INICIANDO DOWNLOAD DIÁRIO")
    logger.info("=" * 50)

    api = PortalTransparenciaAPI()
    db = DatabaseManager()

    try:
        total = baixar_dia_anterior(db, api)

        stats = db.get_estatisticas()

        logger.info("DOWNLOAD CONCLUÍDO COM SUCESSO!")
        logger.info(f"Total inserido: {total} registros")

        for fase_data in stats['por_fase']:
            logger.info(
                f"  {fase_data['fase'].upper()}: "
                f"{fase_data['num_registros']} registros, "
                f"R$ {fase_data.get('total_pago', 0):,.2f}"
            )

    except Exception as e:
        logger.error(f"ERRO NO DOWNLOAD: {e}", exc_info=True)


def main():
    """Função principal do scheduler"""
    logger.info("Scheduler iniciado")
    logger.info("Horário de execução configurado: 06:00 todos os dias")
    logger.info("Para executar imediatamente, use: python scraper.py")

    # Agendar execução diária às 6:00
    schedule.every().day.at("06:00").do(job_baixar_dados)

    # Executar uma vez na inicialização para teste (opcional)
    # Descomente a linha abaixo para executar imediatamente ao iniciar
    # job_baixar_dados()

    logger.info("Aguardando próximo agendamento...")

    while True:
        schedule.run_pending()
        time.sleep(60)  # Verificar a cada minuto


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Scheduler interrompido pelo usuário")
