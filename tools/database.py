import logging
import mysql.connector
import requests
from mysql.connector import pooling
from flask import jsonify
from tools.functions import get_env_variable
from tools.user_config import user_config, user_config_number

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("app.log"),  # Salva os logs em um arquivo
        logging.StreamHandler()  # Exibe os logs no console
    ]
)

pool = pooling.MySQLConnectionPool(
    host=get_env_variable('HOSTGATOR_HOST'),
    port=int(get_env_variable('HOSTGATOR_PORT')),
    user=get_env_variable('USER'),
    password=get_env_variable('PASSWORD'),
    database=get_env_variable('DATABASE')
)


def execute_query(query, params):
    try:
        logging.info(f"Executando query: {query} com parâmetros: {params}")
        connection = pool.get_connection()
        cursor = connection.cursor()
        cursor.execute(query, params)
        connection.commit()
        logging.info("Query executada com sucesso.")
        return cursor
    except mysql.connector.Error as error:
        logging.error(f"Erro de banco de dados: {error}")
        return None
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def store_token(refresh_token, access_token, user_id):
    config = user_config.get(user_id)
    if config:
        table = config['table']
        query = f'INSERT INTO {table} (refresh_token, access_token) VALUES (%s, %s)'
        cursor = execute_query(query, (refresh_token, access_token))
        if cursor:
            logging.info(f"Tokens armazenados com sucesso para user_id: {user_id}")
            return jsonify({'message': 'Tokens armazenados com sucesso', 'id': cursor.lastrowid}), 200
        else:
            logging.error(f"Erro ao armazenar tokens para user_id: {user_id}")
            return jsonify({'error': 'Erro ao armazenar tokens'}), 500

def get_access_token(user_id):
    config = user_config.get(user_id)
    if config:
        table = config['table']
        query = f'SELECT access_token FROM {table} ORDER BY id DESC LIMIT 1'
        logging.info(f"Buscando access_token para user_id: {user_id}")
        
        connection = pool.get_connection()
        try:
            cursor = connection.cursor()
            cursor.execute(query, ())
            result = cursor.fetchone()
            if result:
                logging.info(f"Access token encontrado para user_id: {user_id}")
            else:
                logging.warning(f"Nenhum access token encontrado para user_id: {user_id}")
            return result[0] if result else None
        except mysql.connector.Error as error:
            logging.error(f"Erro de banco de dados: {error}")
            return None
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()
    return None

def get_access_token_number(user_id):
    config = user_config_number.get(user_id)
    if config:
        table = config['table']
        query = f'SELECT access_token FROM {table} ORDER BY id DESC LIMIT 1'
        logging.info(f"Buscando access_token para user_id: {user_id}")
        
        connection = pool.get_connection()
        try:
            cursor = connection.cursor()
            cursor.execute(query, ())
            result = cursor.fetchone()
            if result:
                logging.info(f"Access token encontrado para user_id: {user_id}")
            else:
                logging.warning(f"Nenhum access token encontrado para user_id: {user_id}")
            return result[0] if result else None
        except mysql.connector.Error as error:
            logging.error(f"Erro de banco de dados: {error}")
            return None
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()
    return None

def get_refresh_token(user_id):
    config = user_config.get(user_id)
    if not config:
        error_message = f"Nenhuma configuração encontrada para user_id: {user_id}"
        logging.error(error_message)
        raise ValueError(error_message)  # Lança uma exceção se a configuração não for encontrada.

    table = config['table']
    query = f'SELECT refresh_token FROM {table} ORDER BY id DESC LIMIT 1'
    logging.info(f"Buscando refresh_token para user_id: {user_id}")

    connection = pool.get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(query)
            result = cursor.fetchone()
            if result:
                refresh_token = result[0]
                logging.info(f"Refresh token encontrado para user_id: {user_id}: {refresh_token}")
                return refresh_token
            else:
                error_message = f"Nenhum refresh token encontrado para user_id: {user_id}"
                logging.warning(error_message)
                raise ValueError(error_message)  # Lança uma exceção se o token não for encontrado.
    except mysql.connector.Error as error:
        logging.error(f"Erro de banco de dados ao buscar refresh token: {error}")
        raise  # Repropaga a exceção para alertar sobre falha no banco de dados.
    finally:
        if connection.is_connected():
            connection.close()

def update_tokens(user_id, refresh_token):
    config = user_config.get(user_id)
    if config:
        url = 'https://api.mercadolibre.com/oauth/token'
        headers = {
            'accept': 'application/json',
            'content-type': 'application/x-www-form-urlencoded'
        }
        data = {
            'grant_type': 'refresh_token',
            'client_id': get_env_variable(config['app_id']),
            'client_secret': get_env_variable(config['secret_key']),
            'refresh_token': refresh_token
        }

        logging.info(f"Atualizando tokens para user_id: {user_id} com refresh_token: {refresh_token}")
        response = requests.post(url, headers=headers, data=data)
        if response.status_code == 200:
            tokens = response.json()
            access_token = tokens.get('access_token')
            refresh_token = tokens.get('refresh_token')
            if access_token and refresh_token:
                logging.info(f"Tokens atualizados com sucesso para user_id: {user_id}")
                store_token(refresh_token, access_token, user_id)
                return access_token
        else:
            logging.error(f"Erro ao atualizar tokens: {response.status_code} - {response.text}")
        return None

def store_notification_data(data):
    query = '''
        INSERT INTO perguntas (loja, pergunta, data_pergunta, item_id, resposta, data_resposta, id_cliente)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    '''
    params = (
        data['seller_id'], data['text'], data['date_created'], data['item_id'],
        data['answer_text'], data['answer_date_created'], data['from_id']
    )
    cursor = execute_query(query, params)
    if cursor:
        logging.info(f"Notificação armazenada com sucesso: {data}")
    else:
        logging.error("Erro ao armazenar notificação")
