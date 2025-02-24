import logging
import sys
from flask import request, render_template, redirect, url_for, flash, session
from functools import wraps
import mysql.connector
import os

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  
stderr_handler = logging.StreamHandler(sys.stderr)
stderr_handler.setLevel(logging.INFO)  
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
stderr_handler.setFormatter(formatter)
logger.addHandler(stderr_handler)

if len(logger.handlers) > 1:
    logger.handlers = [stderr_handler]

db_config = {
    'user': os.getenv('USER'),
    'password': os.getenv('PASSWORD'),
    'host': os.getenv('HOSTGATOR_HOST'),
    'database': os.getenv('DATABASE')
}


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            flash('Você precisa estar logado para acessar esta página.')
            return redirect(url_for('login_bot'))
        return f(*args, **kwargs)
    return decorated_function

def insert_user(user, email, password):
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        query = """
        INSERT INTO users_bot (name, email, password) 
        VALUES (%s, %s, %s)
        """
        cursor.execute(query, (user, email, password))
        conn.commit()

        cursor.close()
        conn.close()
        return True
    except mysql.connector.Error as err:
        logger.error(f"Erro ao inserir usuário: {err}")
        return False

def validate_login(user, email, password):
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)

    query = """
    SELECT * FROM users_bot 
    WHERE name = %s AND email = %s AND password = %s
    """
    cursor.execute(query, (user, email, password))
    result = cursor.fetchone()

    cursor.close()
    conn.close()

    return result

def init_view_routes(app):

    @app.route('/menu')
    @login_required
    def menu():
        logger.info("menu page accessed")
        return render_template('menu.html')

    @app.route('/', methods=['GET', 'POST'])
    def login_bot():
        logger.info("chatbot page accessed")
        if request.method == 'POST':
            user = request.form['user']
            email = request.form['email']
            password = request.form['password']

            if validate_login(user, email, password):
                session['logged_in'] = True
                session['user'] = user  # Armazena o nome do usuário na sessão
                logger.info('Login realizado com sucesso!')
                return redirect(url_for('get_perguntas'))  # Redireciona para a página protegida
            else:
                logger.info('Nome de usuário, email ou senha inválidos.')
                flash('Nome de usuário, email ou senha inválidos.')
                return render_template('chatbot.html')

        return render_template('chatbot.html')

    @app.route('/cadastro', methods=['GET', 'POST'])
    def cadastro():
        logger.info("Cadastro page accessed")
        if request.method == 'POST':
            user = request.form['user']
            email = request.form['email']
            password = request.form['password']
            confirm_password = request.form['confirm_password']

            if password != confirm_password:
                logger.warning('As senhas não coincidem.')
                flash('As senhas não coincidem. Tente novamente.', 'danger')
                return render_template('cadastro.html')

            if insert_user(user, email, password):
                logger.info('Usuário cadastrado com sucesso!')
                flash('Cadastro realizado com sucesso!', 'success')
                return redirect(url_for('login_bot'))
            else:
                logger.error('Erro ao cadastrar o usuário.')
                flash('Erro ao cadastrar o usuário. Tente novamente.', 'danger')

        logger.info('Página de cadastro acessada!')
        return render_template('cadastro.html')

    @app.route('/logout')
    def logout():
        session.clear()
        flash('Você foi desconectado.', 'success')
        return redirect(url_for('login_bot'))
    
    @app.route('/dashboards')
    @login_required
    def dash_vendas():
        logger.info("Dash page accessed")
        return render_template('dash_vendas.html')
    
    @app.route('/marketplace')
    @login_required
    def marketplace():
        logger.info("Marketplace page accessed")
        return render_template('marketplace.html')
    
    @app.route('/whatsapp')
    @login_required
    def whatsapp():
        logger.info("Whatsapp page accessed")
        return render_template('whats.html')
    
        