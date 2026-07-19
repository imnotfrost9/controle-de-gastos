import os
import sqlite3
import datetime
import uuid
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# CHAVE DE SESSÃO SEGURA (Proteção contra roubo de cookies)
app.secret_key = 'K9#mP2$vL5@qX7*tY1!wR4%zZ0^cN'

# ==========================================
# CONFIGURAÇÃO DO BANCO DE DADOS (SQLite)
# ==========================================
BANCO_DADOS = 'dados.db'

def conectar_banco():
    conn = sqlite3.connect(BANCO_DADOS)
    # Permite acessar os dados pelos nomes das colunas (como se fosse um dicionário)
    conn.row_factory = sqlite3.Row 
    return conn

def inicializar_banco():
    conn = conectar_banco()
    c = conn.cursor()
    # Cria a tabela de usuários (se não existir)
    c.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            usuario TEXT PRIMARY KEY,
            senha TEXT NOT NULL
        )
    ''')
    # Cria a tabela de gastos (se não existir)
    c.execute('''
        CREATE TABLE IF NOT EXISTS gastos (
            id TEXT PRIMARY KEY,
            usuario TEXT NOT NULL,
            descricao TEXT NOT NULL,
            valor REAL NOT NULL,
            tipo TEXT NOT NULL,
            categoria TEXT NOT NULL,
            data TEXT NOT NULL,
            fixo TEXT
        )
    ''')
    conn.commit()
    conn.close()

# Roda a função para garantir que o banco existe assim que o código liga
inicializar_banco()


# ==========================================
# ROTAS DE AUTENTICAÇÃO (LOGIN E CADASTRO)
# ==========================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form['usuario'].lower() # Transforma em minúsculo para evitar erros
        senha = request.form['senha']
        
        conn = conectar_banco()
        # Busca o usuário no banco de dados
        user_db = conn.execute('SELECT * FROM usuarios WHERE usuario = ?', (usuario,)).fetchone()
        conn.close()
        
        # VERIFICAÇÃO DE SENHA CRIPTOGRAFADA
        if user_db and check_password_hash(user_db['senha'], senha):
            session['usuario'] = usuario
            return redirect(url_for('index'))
        else:
            return render_template('login.html', erro="Usuário ou senha incorretos.")
            
    return render_template('login.html')

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        usuario = request.form['usuario'].lower()
        senha = request.form['senha']
        
        conn = conectar_banco()
        user_db = conn.execute('SELECT * FROM usuarios WHERE usuario = ?', (usuario,)).fetchone()
        
        if user_db:
            conn.close()
            return render_template('cadastro.html', erro="Este usuário já existe.")
        
        # CRIPTOGRAFANDO A SENHA ANTES DE SALVAR
        senha_criptografada = generate_password_hash(senha)
        
        conn.execute('INSERT INTO usuarios (usuario, senha) VALUES (?, ?)', (usuario, senha_criptografada))
        conn.commit()
        conn.close()
        
        return render_template('cadastro.html', sucesso="Conta criada com sucesso! Faça o login.")
        
    return render_template('cadastro.html')

@app.route('/sair')
def sair():
    session.pop('usuario', None)
    return redirect(url_for('login'))


# ==========================================
# ROTA PRINCIPAL (DASHBOARD E GRÁFICOS)
# ==========================================
@app.route('/')
def index():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    
    usuario_atual = session['usuario']
    
    # Busca os gastos apenas do usuário logado e converte para dicionário
    conn = conectar_banco()
    gastos_db = conn.execute('SELECT * FROM gastos WHERE usuario = ?', (usuario_atual,)).fetchall()
    conn.close()
    
    # Mantém a lógica transformando os dados do banco em uma lista de dicionários
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
                           dados=dados_atual,
                           total_entradas=total_entradas,
                           total_saidas=total_saidas,
                           saldo_total=saldo_total,
                           entradas_anterior=entradas_anterior,
                           saidas_anterior=saidas_anterior,
                           mes_atual=mes_atual,
                           ano_atual=ano_atual,
                           nome_mes_atual=nome_mes_atual)


# ==========================================
# ROTAS DE AÇÕES (ADICIONAR E DELETAR)
# ==========================================
@app.route('/adicionar', methods=['POST'])
def adicionar():
    if 'usuario' not in session:
        return redirect(url_for('login'))
        
    usuario_atual = session['usuario']
    descricao = request.form['descricao']
    valor = float(request.form['valor'].replace(',', '.'))
    tipo = request.form['tipo']
    categoria = request.form['categoria']
    fixo = request.form.get('fixo', 'nao')
    
    mes = int(request.form.get('mes', datetime.datetime.now().month))
    ano = int(request.form.get('ano', datetime.datetime.now().year))
    
    if mes == datetime.datetime.now().month and ano == datetime.datetime.now().year:
        data_registro = datetime.datetime.now().strftime("%d/%m/%Y")
    else:
        data_registro = f"01/{mes:02d}/{ano}"
        
    novo_id = str(uuid.uuid4())
    
    # Salva diretamente no banco de dados SQLite
    conn = conectar_banco()
    conn.execute('''
        INSERT INTO gastos (id, usuario, descricao, valor, tipo, categoria, data, fixo) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (novo_id, usuario_atual, descricao, valor, tipo, categoria, data_registro, fixo))
    conn.commit()
    conn.close()
    
    return redirect(url_for('index', mes=mes, ano=ano))

@app.route('/deletar/<id_item>')
def deletar(id_item):
    if 'usuario' not in session:
        return redirect(url_for('login'))
        
    usuario_atual = session['usuario']
    mes = request.args.get('mes', datetime.datetime.now().month)
    ano = request.args.get('ano', datetime.datetime.now().year)
    
    # Apaga do banco de dados garantindo que o usuário só apaga os próprios gastos
    conn = conectar_banco()
    conn.execute('DELETE FROM gastos WHERE id = ? AND usuario = ?', (id_item, usuario_atual))
    conn.commit()
    conn.close()
    
    return redirect(url_for('index', mes=mes, ano=ano))


# ==========================================
# INICIALIZAÇÃO DO SERVIDOR (CONFIGURADO PARA O REPLIT)
# ==========================================
if __name__ == '__main__':
    # Porta 8080 e host 0.0.0.0 liberam a porta correta para o Replit colocar online
    app.run(debug=True, host='0.0.0.0', port=8080)