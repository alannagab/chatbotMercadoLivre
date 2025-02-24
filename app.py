from flask import Flask
from flask_cors import CORS
import sys
import os
import logging

# Configuração básica do logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO) 

# Configura o StreamHandler para enviar logs para stderr
stderr_handler = logging.StreamHandler(sys.stderr)
stderr_handler.setLevel(logging.INFO) 
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
stderr_handler.setFormatter(formatter)
logger.addHandler(stderr_handler)

if len(logger.handlers) > 1:
    logger.handlers = [stderr_handler]

from routes.auth_routes import init_auth_routes
from routes.notification import init_notification_routes
from routes.views import init_view_routes
from routes.perguntas import init_questions_routes

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__)
app.secret_key = app.secret_key = os.getenv('FLASK_SECRET')
CORS(app)  # Habilitar CORS para todas as rotas

init_auth_routes(app)
init_notification_routes(app)
init_view_routes(app)
init_questions_routes(app)

if __name__ == '__main__':
    app.run(debug=True)
