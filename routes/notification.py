from flask import request, jsonify
from tools.notification import notification_queue
import traceback
import logging
import sys

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  
stderr_handler = logging.StreamHandler(sys.stderr)
stderr_handler.setLevel(logging.INFO)  
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
stderr_handler.setFormatter(formatter)
logger.addHandler(stderr_handler)


if len(logger.handlers) > 1:
    logger.handlers = [stderr_handler]

def init_notification_routes(app):

    @app.route('/notification', methods=['GET', 'POST'])
    def notificationPage():
        if request.method == 'POST':
            logger.info("Recebida requisição POST para /notification")
            try:
                body = request.json
                logger.info(f"Corpo da requisição: {body}")
                notification_queue.put(body)
                logger.info("Notificação enfileirada com sucesso")
                return jsonify({"status": "success", "message": "Notificação recebida e enfileirada"}), 200
            except Exception as e:
                logger.error(f"Ocorreu um erro inesperado: {e}")
                traceback.print_exc()
                return jsonify({"status": "error", "message": "Erro inesperado"}), 500
        else:
            logger.warning("Requisição GET recebida para /notification, mas foi descartada")
            return jsonify({"status": "ignored", "message": "Notificação descartada"}), 200

    @app.route('/queue_size', methods=['GET'])
    def queue_size():
        size = notification_queue.qsize()
        logger.info(f"Tamanho atual da fila: {size}")
        return jsonify({"status": "success", "queue_size": size}), 200

    return app
