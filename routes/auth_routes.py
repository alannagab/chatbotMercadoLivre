import requests
import sys
import logging
from dotenv import load_dotenv
from tools.utils import redirect_urls
from tools.functions import get_access_token
from tools.database import store_token
from routes.views import login_required
from flask import render_template, request, redirect, jsonify
from tools.user_config import user_config, oz_user_id, may_user_id, kelan_user_id, camargo_user_id 

load_dotenv()

# Configuração básica do logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
stderr_handler = logging.StreamHandler(sys.stderr)
stderr_handler.setLevel(logging.INFO)  
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
stderr_handler.setFormatter(formatter)
logger.addHandler(stderr_handler)

# Evitar duplicação de handlers
if len(logger.handlers) > 1:
    logger.handlers = [stderr_handler]

def init_auth_routes(app):
    @app.route('/login_meli', methods=['GET'])
    @login_required
    def login():
        logger.info("Login page accessed")
        return render_template('login_meli.html')
    
    @app.route('/login', methods=['POST'])
    @login_required
    def handle_login():
        username = request.form.get('username')
        logger.info(f"Username received: {username}")

        if username in redirect_urls:
            logger.info(f"User {username} redirected to: {redirect_urls[username]}")
            return redirect(redirect_urls[username])
        else:
            logger.warning(f"Invalid username attempted: {username}")
            return render_template('error.html'), 400
        
    @app.route('/authenticate', methods=['POST', 'GET'])
    @login_required
    def handle_token():
        token = request.args.get('code')
        if token:
            try:
                user_id = int(token.split('-')[-1])
                logger.info(f"Token received: {token}")
                logger.info(f"User ID extracted: {user_id}")

                if user_id in [kelan_user_id, camargo_user_id, oz_user_id, may_user_id]:
                    auth_code = token
                    token_response = get_access_token(user_id, auth_code)
                    logger.info(f"Access token for user {user_id}: {token_response}")

                    refresh_token = token_response.get('refresh_token')
                    access_token = token_response.get('access_token')

                    if refresh_token:
                        store_response = store_token(refresh_token, access_token, user_id)
                        logger.info(f"Token storage response for user {user_id}: {store_response}")
                    return render_template('success.html')
                else:
                    logger.warning(f"User ID not recognized: {user_id}")
                    return render_template('error.html'), 404
            except requests.exceptions.RequestException as e:
                logger.error(f"An error occurred during token processing: {e}")
                return render_template('error.html'), 500
            except ValueError as e:
                logger.error(f"Invalid user ID format: {e}")
                return render_template('error.html'), 400
        else:
            logger.warning("No token found in the request")
            return render_template('error.html'), 400

    return app
