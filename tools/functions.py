import os
import requests
import pytz
import json
import logging
import sys  
from datetime import datetime, timedelta
from dotenv import load_dotenv, set_key
from tools.utils import prompts, intentions
from tools.user_config import user_config

load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  
stderr_handler = logging.StreamHandler(sys.stderr)
stderr_handler.setLevel(logging.INFO) 
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
stderr_handler.setFormatter(formatter)
logger.addHandler(stderr_handler)

if len(logger.handlers) > 1:
    logger.handlers = [stderr_handler]

def get_env_variable(key):
    return os.getenv(key)

def set_env_variable(key, value):
    dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    set_key(dotenv_path, key, value)

def get_access_token(user_id, auth_code):
    if user_id not in user_config:
        raise ValueError("Invalid user ID")

    config = user_config[user_id]
    url = 'https://api.mercadolibre.com/oauth/token'

    headers = {
        'accept': 'application/json',
        'content-type': 'application/x-www-form-urlencoded',
    }

    data = {
        'grant_type': 'authorization_code',
        'client_id': os.getenv(config['app_id']),
        'client_secret': os.getenv(config['secret_key']),
        'code': auth_code,
        'redirect_uri': os.getenv('REDIRECT_URI')
    }

    response = requests.post(url, headers=headers, data=data)

    if response.status_code == 200:
        return response.json()
    else:
        response.raise_for_status()


def get_received_questions(user_id, access_token):
    logger.info(f'Notificação recebida do usuário: {user_id}')

    # Obter a data atual e o dia anterior em UTC
    current_time = datetime.now(pytz.UTC)
    previous_day = current_time - timedelta(days=1)
    status = "UNANSWERED"

    # Formatando as datas para strings ISO
    current_time_str = current_time.isoformat()
    previous_day_str = previous_day.isoformat()

    url = f"https://api.mercadolibre.com/my/received_questions/search"
    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    params = {
        "status": status,
        "date_created_from": previous_day_str,
        "date_created_to": current_time_str
    }

    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200:
        data = response.json()
        logger.info("Dados recebidos com sucesso da API Mercado Libre")
        
        extracted_data = []
        for question in data['questions']:
            question_id = question['id']
            item_id = question['item_id']
            client_id = question['from']['id']
            text = question['text']
            
            client_info = get_client_info(client_id, access_token)
            item_description = get_item_description(item_id, access_token)
            item_details = get_item_details(item_id, access_token)

            extracted_data.append({
                "client_id": client_id,
                "text": text,
                "item_id": item_id,
                "question_id": question_id,
                "client_info": client_info,
                "item_description": item_description,
                "item_details": item_details,
            })
        
        #Converter os dados extraídos para JSON
        extracted_data_json = json.dumps(extracted_data, ensure_ascii=False, indent=4)
        logger.info(f"Dados extraídos: {extracted_data_json}")
        return response  # Retornar a resposta original do request

    else:
        logger.error(f"Request falhou com o código de status: {response.status_code}")
        logger.error(f"URL: {url}")
        logger.error(f"Headers: {headers}")
        logger.error(f"Params: {params}")
        logger.error(f"Response Content: {response.content}")
        return response  
    
def get_client_info(client_id, access_token):
    url = f"https://api.mercadolibre.com/users/{client_id}"
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        logger.info(f"Informações do cliente {client_id} obtidas com sucesso")
        return response.json()
    else:
        logger.error(f"Erro ao obter informações do cliente {client_id}: {response.status_code}")
        return {}

def get_item_description(item_id, access_token):
    url = f"https://api.mercadolibre.com/items/{item_id}/description"
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        description = response.json().get('plain_text', '')
        logger.info(f"Descrição do item {item_id} obtida com sucesso")
        return description
    else:
        logger.error(f"Erro ao obter descrição do item {item_id}: {response.status_code}")
        return ""

def get_item_details(item_id, access_token):
    url = f"https://api.mercadolibre.com/items/{item_id}"
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        item_data = response.json()
        logger.info(f"Detalhes do item {item_id} obtidos com sucesso")
        # Selecionar apenas os campos de interesse
        selected_data = {
            "item_title": item_data.get("title"),
            "category_id": item_data.get("category_id"),
            "available_quantity": item_data.get("available_quantity"),
            "warranty_time": next((term.get("value_name") for term in item_data.get("sale_terms", []) if term.get("id") == "WARRANTY_TIME"), None),
            "item_condition": item_data.get("condition"),
            "pictures": [picture.get("url") for picture in item_data.get("pictures", [])],
            "attributes": [
                {
                    "name": attribute.get("name"),
                    "value": attribute.get("value_name", "No value")
                } for attribute in item_data.get("attributes", []) if attribute.get("id") in [
                    "MATERIAL", "UNITS_PER_PACK", "BASE_MATERIAL", "BRAND", "DIAMETER", "FINISH", "HEIGHT", "IS_EXTENSIBLE", "IS_KIT", 
                    "IS_SUITABLE_FOR_EXTERIOR", "LENGTH", "REQUIRES_ASSEMBLY", "STYLE", "TOP_MATERIAL", "WEIGHT", "WIDTH"]
            ]
        }
        return selected_data
    else:
        logger.error(f"Erro ao obter detalhes do item {item_id}: {response.status_code}")
        return {}

def post_to_meli(resource, resposta_gpt, access_token):
    try:
        if not access_token:
            raise ValueError("ACCESS_TOKEN não definido ou expirado")

        url = "https://api.mercadolibre.com/answers"
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        data = {
            "question_id": resource,
            "text": resposta_gpt
        }

        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        logger.info(f"Resposta postada com sucesso para a pergunta {resource}")
        return response.json()

    except ValueError as ve:
        logger.error(f"ValueError: {ve}")
        raise

    except requests.exceptions.HTTPError as http_err:
        logger.error(f"HTTP error occurred: {http_err}")
        logger.error(f"Response status code: {response.status_code}")
        logger.error(f"Response content: {response.content}")
        raise

    except requests.exceptions.RequestException as req_err:
        logger.error(f"Request error occurred: {req_err}")
        raise

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        raise

def classify_by_chatgpt(response):
    pergunta = response.get('text')
    logger.info(pergunta)
    api_key = os.getenv('OPENAI_API_KEY')
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    data = {
        "model": "gpt-4o",
        "messages": [
            {
                "role": "system",
                "content": f'de acordo com as palavras chaves {intentions}, classifique o tipo desta pergunta: "{response}", se não conseguir identificar, responda: "Não Identificado"'
            }
        ],
        "max_tokens": 50,
        "temperature": 0.5
    }

    logger.info(f"Enviando solicitação para classificação com GPT-4... {data}")
    try:
        response = requests.post('https://api.openai.com/v1/chat/completions', headers=headers, json=data)
        response.raise_for_status() 
        result = response.json()
        classification = result['choices'][0]['message']['content'].strip()
        logger.info(f"Classificação recebida: {classification}")
        return classification
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro ao classificar com GPT-4: {e}")
        raise

def answer_by_chatgpt(response, classification):
    pergunta = response.get('text')
    client_info = response.get('client_info')
    descricao = response.get('item_description')
    produto = response.get('item_title')
    atributos = response.get('attributes')

    print(pergunta, atributos, client_info, descricao, produto)

    api_key = os.getenv('OPENAI_API_KEY')
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    data = {
        "model": "gpt-4o",
        "temperature": 1,
        "messages": [
            {
                "role": "system",
                "content": f'Você é uma assistente especializada em responder perguntas sobre os produtos de nossa loja de Móveis Decorativos no Mercado Livre. Aqui está a pergunta, nome do usuário, descrição do produto e demais informações, responda a pergunta de acordo com as informações disponíveis: Tipo de pergunta: {classification} Informações gerais {response}, prompts caso não haja a informação:"{prompts}"'
            }
        ],
        "max_tokens": 256
    }

    logger.info(f"Enviando solicitação para responder com GPT-4... {data}")
    try:
        response = requests.post('https://api.openai.com/v1/chat/completions', headers=headers, json=data)
        response.raise_for_status()  
        result = response.json()
        answer = result['choices'][0]['message']['content'].strip()
        usage = result.get('usage', {})
        input_tokens = usage.get('prompt_tokens', 0)
        output_tokens = usage.get('completion_tokens', 0)
        total_tokens = usage.get('total_tokens', input_tokens + output_tokens)

        logger.info(f"Pergunta do cliente: {response}")
        logger.info(f"Resposta do GPT: {answer}")
        logger.info(f"Tokens de entrada: {input_tokens}")
        logger.info(f"Tokens de saída: {output_tokens}")
        logger.info(f"Total de tokens usados: {total_tokens}")
        
        return answer
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro ao responder com GPT-4: {e}")
        raise

