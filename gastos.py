import os
import datetime
import uuid
import psycopg2
import psycopg2.extras
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# CHAVE DE SESSÃO SEGURA
app.secret_key = 'K9#mP2$vL5@qX7*tY1!wR4%zZ0^cN'

DATABASE_URL = os.environ.get('DATABASE_URL')

def conectar_banco():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

def inicializar_banco():
    conn = conectar_banco()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    # Cria a tabela de usuários com suporte a foto de perfil
    cur.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            usuario TEXT PRIMARY KEY,
            senha TEXT NOT NULL,
            foto TEXT
        )
    ''')
    
    # Cria a tabela de gastos
    cur.execute('''
        CREATE TABLE IF NOT EXISTS gastos (
            id TEXT PRIMARY KEY,
            usuario TEXT NOT NULL,
            descricao TEXT NOT NULL,
            valor REAL NOT NULL,
            tipo TEXT NOT NULL,
            categoria TEXT NOT NULL,
            pagamento TEXT,
            data TEXT NOT NULL,
            fixo TEXT
        )
    ''')
    conn.commit()
    cur.close()
    conn.close()

if DATABASE_URL:
    inicializar_banco()


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form['usuario'].lower().strip()
        senha = request.form['senha']
        
        conn = conectar_banco()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute('SELECT * FROM usuarios WHERE usuario = %s', (usuario,))
        user_db = cur.fetchone()
        cur.close()
        conn.close()
        
        if user_db and check_password_hash(user_db['senha'], senha):
            session.clear()
            session['usuario'] = usuario
            return redirect(url_for('index'))
        else:
            return render_template('login.html', erro="Usuário ou senha incorretos.")
            
    return render_template('login.html')

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        usuario = request.form['usuario'].lower().strip()
        senha = request.form['senha']
        
        conn = conectar_banco()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute('SELECT * FROM usuarios WHERE usuario = %s', (usuario,))
        user_db = cur.fetchone()
        
        if user_db:
            cur.close()
            conn.close()
            return render_template('cadastro.html', erro="Este usuário já existe.")
        
        senha_criptografada = generate_password_hash(senha)
        
        # Insere usuário novo com foto vazia padrão
        cur.execute('INSERT INTO usuarios (usuario, senha, foto) VALUES (%s, %s, %s)', 
                    (usuario, senha_criptografada, 'https://cdn-icons-png.flaticon.com/512/149/149071.png'))
        conn.commit()
        
        cur.close()
        conn.close()
        
        return render_template('cadastro.html', sucesso="Conta criada com sucesso! Faça o login.")
        
    return render_template('cadastro.html')

@app.route('/atualizar_foto', methods=['POST'])
def atualizar_foto():
    if 'usuario' not in session:
        return redirect(url_for('login'))
        
    usuario_atual = session['usuario']
    nova_foto = request.form.get('foto_url')
    
    conn = conectar_banco()
    cur = conn.cursor()
    cur.execute('UPDATE usuarios SET foto = %s WHERE usuario = %s', (nova_foto, usuario_atual))
    conn.commit()
    cur.close()
    conn.close()
    
    return redirect(url_for('index'))

@app.route('/sair')
def sair():
    session.clear()
    return redirect(url_for('login'))


@app.route('/')
def index():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    
    usuario_atual = session['usuario']
    
    conn = conectar_banco()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    # Busca dados do usuário (incluindo a foto)
    cur.execute('SELECT * FROM usuarios WHERE usuario = %s', (usuario_atual,))
    user_data = cur.fetchone()
    foto_usuario = user_data['foto'] if user_data and user_data['foto'] else 'https://cdn-icons-png.flaticon.com/512/149/149071.png'
    
    # Busca os gastos
    cur.execute('SELECT * FROM gastos WHERE usuario = %s', (usuario_atual,))
    gastos_db = cur.fetchall()
    
    cur.close()
    conn.close()
    
    dados = [dict(gasto) for gasto in gastos_db]
    
    mes_atual = int(request.args.get('mes', datetime.datetime.now().month))
    ano_atual = int(request.args.get('ano', datetime.datetime.now().year))
    
    if mes_atual == 1:
        mes_anterior = 12
        ano_anterior = ano_atual - 1
    else:
        mes_anterior = mes_atual - 1
        ano_anterior = ano_atual

    sufixo_atual = f"/{mes_atual:02d}/{ano_atual}"
    sufixo_anterior = f"/{mes_anterior:02d}/{ano_anterior}"
    
    dados_atual = [d for d in dados if sufixo_atual in d.get('data', '')]
    total_entradas = sum(item['valor'] for item in dados_atual if item['tipo'] == 'entrada')
    total_saidas = sum(item['valor'] for item in dados_atual if item['tipo'] == 'saida')
    saldo_total = total_entradas - total_saidas
    
    dados_anterior = [d for d in dados if sufixo_anterior in d.get('data', '')]
    entradas_anterior = sum(item['valor'] for item in dados_anterior if item['tipo'] == 'entrada')
    saidas_anterior = sum(item['valor'] for item in dados_anterior if item['tipo'] == 'saida')
    
    meses_nomes = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", 
                   "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    nome_mes_atual = meses_nomes[mes_atual - 1]
    
    return render_template('index.html',
                           usuario_atual=usuario_atual,
                           foto_usuario=foto_usuario,
                           dados=dados_atual,
                           total_entradas=total_entradas,
                           total_saidas=total_saidas,
                           saldo_total=saldo_total,
                           entradas_anterior=entradas_anterior,
                           saidas_anterior=saidas_anterior,
                           mes_atual=mes_atual,
                           ano_atual=ano_atual,
                           nome_mes_atual=nome_mes_atual)


@app.route('/adicionar', methods=['POST'])
def adicionar():
    if 'usuario' not in session:
        return redirect(url_for('login'))
        
    usuario_atual = session['usuario']
    descricao = request.form['descricao']
    valor = float(request.form['valor'].replace(',', '.'))
    tipo = request.form['tipo']
    categoria = request.form['categoria']
    pagamento = request.form.get('pagamento', 'PIX')
    fixo = request.form.get('fixo', 'nao')
    
    mes = int(request.form.get('mes', datetime.datetime.now().month))
    ano = int(request.form.get('ano', datetime.datetime.now().year))
    
    if mes == datetime.datetime.now().month and ano == datetime.datetime.now().year:
        data_registro = datetime.datetime.now().strftime("%d/%m/%Y")
    else:
        data_registro = f"01/{mes:02d}/{ano}"
        
    novo_id = str(uuid.uuid4())
    
    conn = conectar_banco()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO gastos (id, usuario, descricao, valor, tipo, categoria, pagamento, data, fixo) 
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    ''', (novo_id, usuario_atual, descricao, valor, tipo, categoria, pagamento, data_registro, fixo))
    
    conn.commit()
    cur.close()
    conn.close()
    
    return redirect(url_for('index', mes=mes, ano=ano))

@app.route('/deletar/<id_item>')
def deletar(id_item):
    if 'usuario' not in session:
        return redirect(url_for('login'))
        
    usuario_atual = session['usuario']
    mes = request.args.get('mes', datetime.datetime.now().month)
    ano = request.args.get('ano', datetime.datetime.now().year)
    
    conn = conectar_banco()
    cur = conn.cursor()
    cur.execute('DELETE FROM gastos WHERE id = %s AND usuario = %s', (id_item, usuario_atual))
    
    conn.commit()
    cur.close()
    conn.close()
    
    return redirect(url_for('index', mes=mes, ano=ano))


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0')