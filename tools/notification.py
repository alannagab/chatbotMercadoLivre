import queue
import threading
import traceback
import json
import requests
from dotenv import load_dotenv
from tools.functions import get_received_questions, post_to_meli, classify_by_chatgpt, answer_by_chatgpt
from tools.database import get_access_token, get_refresh_token, update_tokens, store_notification_data
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

load_dotenv()

notification_queue = queue.Queue()
lock = threading.Lock()

def process_notifications():
    while True:
        notification = notification_queue.get()
        if notification is None:
            break
        process_notification(notification)
        notification_queue.task_done()

def process_notification(body):
    with lock:
        try:
            logger.info(f"Processando notificação: {body}")
            user_id = body.get('user_id')

            if not user_id:
                logger.warning("User ID não encontrado no corpo da requisição")
                return

            def attempt_to_fetch_questions(access_token):
                update_response = None  
                response = get_received_questions(user_id, access_token)
                if response.status_code == 401:  
                    logger.warning("Token expirado, tentando acessar refresh_token...")
                    refresh_token = get_refresh_token(user_id)
                    if refresh_token: 
                        update_response = update_tokens(user_id, refresh_token)
                    if update_response and update_response.status_code == 200:
                        access_token = get_access_token(user_id)
                        if access_token:
                            return get_received_questions(user_id, access_token)
                        else:
                            raise Exception("Falha ao atualizar o token")
                    else:
                        if update_response:
                            update_response.raise_for_status()  # Levanta uma exceção se o status não for 200
                        else:
                            raise Exception("Não foi possível obter o refresh token ou atualizar os tokens")
                return response

            access_token = get_access_token(user_id)
            response = attempt_to_fetch_questions(access_token)
            if response.status_code != 200:
                raise Exception(f"Failed to fetch questions, status code: {response.status_code}")

            response_data = response.json()
            if not response_data['questions']:
                raise KeyError('Nenhuma pergunta encontrada no JSON recebido')

            classification = classify_by_chatgpt(response_data)
            resposta_gpt = answer_by_chatgpt(response_data, classification)
            sucesso = post_to_meli(response_data['questions'][0]['id'], resposta_gpt, access_token)

            data = {
                'seller_id': sucesso['seller_id'],
                'text': sucesso['text'],
                'item_id': sucesso['item_id'],
                'date_created': sucesso['date_created'],
                'answer_text': sucesso['answer']['text'],
                'answer_date_created': sucesso['answer']['date_created'],
                'from_id': sucesso['from']['id']
            }

            store_notification_data(data)
            logger.info(f"Notificação processada com sucesso: {data}")

        except Exception as e:
            logger.error(f"Ocorreu um erro: {e}")
            try:
                headers = {
                    'Accept': 'application/json',
                    'Content-Type': 'application/json',
                }
                url = ''
                error_data = {"error": str(e)}
                logger.error(f"Erro: {error_data}")
                logger.info(f"Enviando erro para rota /notify-error")

                response = requests.post(url, data=json.dumps(error_data), headers=headers)
                response.raise_for_status()  
                logger.info(f"Resposta recebida: {response.text}") 
            except requests.exceptions.HTTPError as http_err:
                logger.error(f"Erro HTTP ocorrido: {http_err}")
                logger.error(f"Conteúdo da resposta: {response.content}")
            except Exception as e:
                logger.error(f"Ocorreu um erro ao tentar enviar o POST: {e}")
                traceback.print_exc()

notification_thread = threading.Thread(target=process_notifications, daemon=True)
notification_thread.start()
