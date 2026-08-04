import os
from flask import Flask, render_template, request, redirect, url_for, session
import psycopg2
import psycopg2.extras
from datetime import datetime
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.secret_key = 'sua_chave_secreta_super_segura'

# Corrige o erro de "Bad Request" em ambientes de nuvem (como o Render)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

def conectar_banco():
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise ValueError("A variável de ambiente DATABASE_URL não está configurada!")
    return psycopg2.connect(database_url, cursor_factory=psycopg2.extras.DictCursor)

def inicializar_banco():
    conn = conectar_banco()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL,
            foto_url TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS transacoes (
            id SERIAL PRIMARY KEY,
            usuario_id INTEGER REFERENCES usuarios(id),
            descricao TEXT NOT NULL,
            valor NUMERIC(10,2) NOT NULL,
            tipo TEXT NOT NULL,
            categoria TEXT DEFAULT 'Outros',
            pagamento TEXT DEFAULT 'PIX',
            data DATE NOT NULL
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

inicializar_banco()

MESES_NOME = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
}

@app.route('/')
def index():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    usuario_id = session['usuario_id']
    usuario_atual = session['username']
    
    conn = conectar_banco()
    cur = conn.cursor()
    cur.execute("SELECT foto_url FROM usuarios WHERE id = %s", (usuario_id,))
    res_user = cur.fetchone()
    foto_usuario = res_user['foto_url'] if res_user and res_user['foto_url'] else 'https://cdn.pixabay.com/photo/2015/10/05/22/37/blank-profile-picture-973460_1280.png'

    hoje = datetime.today()
    mes_atual = request.args.get('mes', default=hoje.month, type=int)
    ano_atual = request.args.get('ano', default=hoje.year, type=int)
    nome_mes_atual = MESES_NOME.get(mes_atual, "Mês")

    cur.execute("""
        SELECT id, descricao, valor, tipo, categoria, pagamento, TO_CHAR(data, 'DD/MM/YYYY') as data 
        FROM transacoes 
        WHERE usuario_id = %s AND EXTRACT(MONTH FROM data) = %s AND EXTRACT(YEAR FROM data) = %s
        ORDER BY data DESC, id DESC
    """, (usuario_id, mes_atual, ano_atual))
    dados = cur.fetchall()

    total_entradas = sum(item['valor'] for item in dados if item['tipo'] == 'entrada')
    total_saidas = sum(item['valor'] for item in dados if item['tipo'] == 'saida')
    saldo_total = total_entradas - total_saidas

    cur.close()
    conn.close()

    return render_template('index.html', 
                           dados=dados, 
                           total_entradas=total_entradas, 
                           total_saidas=total_saidas, 
                           saldo_total=saldo_total,
                           mes_atual=mes_atual,
                           ano_atual=ano_atual,
                           nome_mes_atual=nome_mes_atual,
                           usuario_atual=usuario_atual,
                           foto_usuario=foto_usuario)

@app.route('/login', methods=['GET', 'POST'])
def login():
    erro = None
    if request.method == 'POST':
        username = request.form['username']
        senha = request.form['senha']

        conn = conectar_banco()
        cur = conn.cursor()
        cur.execute("SELECT * FROM usuarios WHERE username = %s AND senha = %s", (username, senha))
        usuario = cur.fetchone()
        cur.close()
        conn.close()

        if usuario:
            session['usuario_id'] = usuario['id']
            session['username'] = usuario['username']
            return redirect(url_for('index'))
        else:
            erro = "Usuário ou senha incorretos."

    return render_template('login.html', erro=erro)

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    erro = None
    sucesso = None
    if request.method == 'POST':
        username = request.form['username']
        senha = request.form['senha']

        conn = conectar_banco()
        cur = conn.cursor()
        cur.execute("SELECT * FROM usuarios WHERE username = %s", (username,))
        existing_user = cur.fetchone()

        if existing_user:
            erro = "Este nome de usuário já existe. Escolha outro."
        else:
            cur.execute("INSERT INTO usuarios (username, senha) VALUES (%s, %s)", (username, senha))
            conn.commit()
            sucesso = "Cadastro realizado com sucesso! Faça login."
        
        cur.close()
        conn.close()

    return render_template('cadastro.html', erro=erro, sucesso=sucesso)

@app.route('/adicionar', methods=['POST'])
def adicionar():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    usuario_id = session['usuario_id']
    descricao = request.form['descricao']
    valor_str = request.form['valor'].replace(',', '.')
    valor = float(valor_str)
    tipo = request.form['tipo']
    categoria = request.form.get('categoria', 'Outros')
    pagamento = request.form.get('pagamento', 'PIX')
    
    mes = request.form.get('mes', datetime.today().month, type=int)
    ano = request.form.get('ano', datetime.today().year, type=int)
    
    hoje = datetime.today()
    if mes == hoje.month and ano == hoje.year:
        data_transacao = hoje.date()
    else:
        data_transacao = datetime(ano, mes, 1).date()

    conn = conectar_banco()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO transacoes (usuario_id, descricao, valor, tipo, categoria, pagamento, data) 
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (usuario_id, descricao, valor, tipo, categoria, pagamento, data_transacao))
    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for('index', mes=mes, ano=ano))

@app.route('/atualizar_foto', methods=['POST'])
def atualizar_foto():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    usuario_id = session['usuario_id']
    foto_url = request.form['foto_url']

    conn = conectar_banco()
    cur = conn.cursor()
    cur.execute("UPDATE usuarios SET foto_url = %s WHERE id = %s", (foto_url, usuario_id))
    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for('index'))

@app.route('/deletar/<int:id>')
def deletar(id):
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    mes = request.args.get('mes', datetime.today().month, type=int)
    ano = request.args.get('ano', datetime.today().year, type=int)

    conn = conectar_banco()
    cur = conn.cursor()
    cur.execute("DELETE FROM transacoes WHERE id = %s AND usuario_id = %s", (id, session['usuario_id']))
    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for('index', mes=mes, ano=ano))

@app.route('/sair')
def sair():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)