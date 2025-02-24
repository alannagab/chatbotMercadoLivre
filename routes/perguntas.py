import os
import requests
import logging
import mysql.connector
from datetime import datetime
from flask import Flask, request, render_template
from routes.views import login_required
from tools.user_config import user_config_number
from tools.database import get_access_token, get_access_token_number
import traceback

app = Flask(__name__)

# Configuração do logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configurações do banco de dados
db_config = {
    'host': os.getenv('HOSTGATOR_HOST'),
    'port': os.getenv('HOSTGATOR_PORT'),
    'user': os.getenv('USER'),
    'password': os.getenv('PASSWORD'),
    'database': os.getenv('DATABASE')
}

# Mapeamento de IDs de lojas para nomes
loja_map = {
    '65131481': 'Kelan Móveis',
    '271842978': 'May Store',
    '20020278': 'Oz Shop',
    '190581815': 'Camargo Decore'
}

def convert_minutes_to_hours(minutes):
    if minutes is not None:
        if minutes >= 60:
            hours = minutes / 60
            return f"{round(hours, 2)} horas"
        else:
            return f"{minutes} minutos"
    else:
        return None

def format_date(date_str):
    try:
        date_obj = datetime.fromisoformat(date_str)
        formatted_date = date_obj.strftime('%d/%m/%Y %H:%M:%S')
        logger.info(f"Data formatada com sucesso: {formatted_date}")
        return formatted_date
    except ValueError as e:
        logger.warning(f"Erro ao formatar data: {date_str}, erro: {e}")
        return date_str

def get_response_time(user_id):
    access_token = get_access_token_number(user_id)
    
    if not access_token:
        logger.error(f"Nenhum access token encontrado para o user_id: {user_id}")
        return {'error': 'Access token não encontrado'}
    else:
        # Imprime apenas os primeiros e últimos 4 caracteres do token para segurança
        masked_token = f"{access_token[:4]}****{access_token[-4:]}"
        logger.info(f"Access token obtido para user_id {user_id}: {masked_token}")
    
    url = f'https://api.mercadolibre.com/users/{user_id}/questions/response_time'
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    
    response = requests.get(url, headers=headers)
    
    logger.info(f"Status da resposta da API: {response.status_code}")
    logger.debug(f"Texto da resposta da API: {response.text}")
    
    if response.status_code == 200:
        data = response.json()
        logger.info(f"Dados da resposta da API: {data}")
        return data
    else:
        error_message = f'Erro: {response.status_code} - {response.text}'
        logger.error(f"Erro ao obter tempo de resposta: {error_message}")
        return {'error': error_message}

def init_questions_routes(app):
    @app.route('/perguntas', methods=['GET'])
    @login_required
    def get_perguntas():
        try:
            logger.info("Conectando ao banco de dados...")
            conn = mysql.connector.connect(**db_config)
            cursor = conn.cursor(dictionary=True)
            
            # Captura os parâmetros da requisição
            sort_by_name = request.args.get('sort_by')
            order_by = request.args.get('order_by', 'data_resposta DESC')
            user_id = request.args.get('user_id')  # Novo parâmetro
            
            logger.info(f"Parâmetros recebidos - sort_by_name: {sort_by_name}, order_by: {order_by}, user_id: {user_id}")
            
            # Mapeia o nome da loja para o ID correspondente
            sort_by_id = None
            for key, value in loja_map.items():
                if value == sort_by_name:
                    sort_by_id = key
                    break
            
            logger.info(f"Loja mapeada para ID: {sort_by_id}")
            
            # Processa as perguntas conforme o filtro de loja
            if sort_by_id:
                logger.info(f"Filtrando perguntas para a loja ID: {sort_by_id}")
                sql = f'SELECT * FROM perguntas WHERE loja = %s ORDER BY {order_by}'
                cursor.execute(sql, (sort_by_id,))
            else:
                logger.info("Recuperando todas as perguntas sem filtro de loja")
                sql = f'SELECT * FROM perguntas ORDER BY loja, {order_by}'
                cursor.execute(sql)
            
            results = cursor.fetchall()
            logger.info(f"Número de perguntas recuperadas: {len(results)}")
            
            for result in results:
                logger.info(f"Pergunta: {result}")
                result['data_pergunta'] = format_date(result['data_pergunta'])
                result['data_resposta'] = format_date(result['data_resposta'])
                result['loja'] = loja_map.get(result['loja'], result['loja'])
            
            # Inicializa a variável para o tempo de resposta
            response_time_data = None
            
            # Se um user_id for recebido, chama a função get_response_time
            if user_id:
                logger.info(f"Obtendo tempo de resposta para user_id: {user_id}")
                response_time_data = get_response_time(user_id)
                logger.info(f"Tempo de resposta obtido: {response_time_data}")

                # Verifica se não há erro na resposta
                if 'error' not in response_time_data:
    # Converte os tempos de resposta
                    response_time_data_converted = {}
                    response_time_data_converted['user_id'] = response_time_data['user_id']
                    response_time_data_converted['total'] = {
                        'response_time': convert_minutes_to_hours(response_time_data['total']['response_time'])
                    }
                    response_time_data_converted['weekend'] = {
                        'response_time': convert_minutes_to_hours(response_time_data['weekend']['response_time']),
                        'sales_percent_increase': response_time_data['weekend']['sales_percent_increase']
                    }
                    response_time_data_converted['weekdays_working_hours'] = {
                        'response_time': convert_minutes_to_hours(response_time_data['weekdays_working_hours']['response_time']),
                        'sales_percent_increase': response_time_data['weekdays_working_hours']['sales_percent_increase']
                    }
                    response_time_data_converted['weekdays_extra_hours'] = {
                        'response_time': convert_minutes_to_hours(response_time_data['weekdays_extra_hours']['response_time']),
                        'sales_percent_increase': response_time_data['weekdays_extra_hours']['sales_percent_increase']
                    }
                    # Substitui response_time_data pelos dados convertidos
                    response_time_data = response_time_data_converted   
                else:
                    logger.error(f"Erro na resposta da API: {response_time_data['error']}")
            else:
                logger.info("Nenhum user_id recebido; não obtendo tempo de resposta")

            logger.info("Renderizando template com perguntas e tempo de resposta")
            return render_template(
                'perguntas.html',
                perguntas=results,
                loja_map=loja_map,
                response_time_data=response_time_data,
                selected_user_id=user_id,
                sort_by_name=sort_by_name,
                order_by=order_by
            )
            
        except mysql.connector.Error as err:
            logger.error(f"Erro ao buscar dados: {err}")
            return 'Erro ao buscar dados', 500
        except Exception as e:
            logger.error(f"Exceção não tratada: {e}")
            traceback_str = traceback.format_exc()
            logger.error(f"Stack trace: {traceback_str}")
            return 'Erro interno do servidor', 500
        finally:
            if cursor:
                cursor.close()
                logger.info("Cursor do banco de dados fechado")
            if conn and conn.is_connected():
                conn.close()
                logger.info("Conexão com o banco de dados fechada")

    return app
