from data.db import conectar
from werkzeug.security import check_password_hash, generate_password_hash
from flask import Flask, render_template, request, redirect, url_for, flash, session
from functools import wraps

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = "josejoaquimdasilvafilho"

from functools import wraps
from flask import session, redirect, url_for, flash

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("usuario"):
            flash("Faça login primeiro!")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper

def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("usuario"):
            flash("Faça login primeiro!")
            return redirect(url_for("login"))
        if session.get("perfil") != "admin":
            flash("Acesso restrito a administradores.")
            return redirect(url_for("home"))
        return f(*args, **kwargs)
    return wrapper


def atualizar_produtos():
    conn = conectar()
    cur = conn.cursor()

    from datetime import datetime, timedelta

    hoje = datetime.now().date()
    limite_alerta = hoje + timedelta(days=7)

    cur.execute("""
        UPDATE produtos
        SET status_validade = 'vencido'
        WHERE date(data_validade) < date(?) AND ativo=1
    """, (hoje,))

    cur.execute("""
        UPDATE produtos
        SET status_validade = 'próximo do vencimento'
        WHERE date(data_validade) BETWEEN date(?) AND date(?) AND ativo=1
    """, (hoje, limite_alerta))

    cur.execute("""
        UPDATE produtos
        SET status_validade = 'válido'
        WHERE date(data_validade) > date(?) AND ativo=1
    """, (limite_alerta,))

    conn.commit()
    conn.close()


@app.route("/", methods=["GET", "POST"])
def criar_admin():
    conn = conectar()
    cur = conn.cursor()

    cur.execute("Select Count(*) From usuarios")

    if cur.fetchone()[0] > 0:
        flash("Admin já existente.")
        return redirect(url_for("login"))
    
    if request.method == "POST":
        empresa = request.form["empresa"]
        nome = request.form["nome"]
        usuario = request.form["usuario"]
        senha = generate_password_hash(request.form["senha"])

        cur.execute("Insert Into usuarios (nome, usuario, senha, perfil, ativo) Values (?, ?, ?, ?, ?)",
            (nome, usuario, senha, "admin", 1),)
        
        cur.execute("Select id, usuario, senha, perfil From usuarios Where usuario=? And ativo=1",(usuario,),)
        user = cur.fetchone()

        session["id"] = user[0]
        session["usuario"] = user[1]
        session["perfil"] = user[3]
        session["empresa"] = empresa

        conn.commit()
        conn.close()
        flash("Administrador criado com sucesso!")

        return redirect(url_for("home"))

    return render_template("inicio/admin.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    conn = conectar()
    cur = conn.cursor()

    if request.method == "POST":
        usuario = request.form["usuario"]
        senha = request.form["senha"]

        cur.execute("Select id, usuario, senha, perfil From usuarios Where usuario=? And ativo=1",(usuario,),)
        user = cur.fetchone()

        if user and check_password_hash(user[2], senha):
            session["id"] = user[0]
            session["usuario"] = user[1]
            session["perfil"] = user[3]

            conn.close()
            return redirect(url_for("home"))
        else:
            flash("Usuário ou senha inválido!")
            conn.close()
            return redirect(url_for("login"))

    return render_template("inicio/login.html")

@app.route("/home", methods=["GET"])
@login_required
def home():
    atualizar_produtos()

    conn = conectar()
    cur = conn.cursor()

    # Total de produtos
    total_produtos = cur.execute("""
        SELECT COUNT(*) FROM produtos WHERE ativo = 1
    """).fetchone()[0] or 0

    # Estoque baixo
    estoque_baixo = cur.execute("""
        SELECT p.nome, e.quantidade
        FROM estoque e
        LEFT JOIN produtos p ON e.produto_id = p.id
        WHERE e.quantidade <= 5 AND p.ativo = 1
        ORDER BY e.quantidade ASC
    """).fetchall()

    # Top 5 mais vendidos
    mais_vendidos = cur.execute("""
        SELECT p.nome, SUM(m.quantidade) AS total_vendido
        FROM movimentacoes m
        JOIN produtos p ON m.produto_id = p.id
        WHERE m.tipo = 'saida'
        GROUP BY p.id
        ORDER BY total_vendido DESC
        LIMIT 5
    """).fetchall()

    # Contagem de quase vencidos
    quase_vencidos = cur.execute("""
        SELECT COUNT(*)
        FROM produtos
        WHERE status_validade = 'próximo do vencimento' and ativo=1;
    """).fetchone()[0]

    # Valor total do estoque
    valor_total = cur.execute("""
        SELECT SUM(p.preco * e.quantidade)
        FROM produtos p
        JOIN estoque e ON p.id = e.produto_id
        WHERE p.ativo = 1
    """).fetchone()[0] or 0

    # LocalView (venc / excesso)
    modo = request.args.get("view", "venc")

    proximosVencimento = None
    excessos = None

    # Exibir próximos ao vencimento
    if modo == "venc":
        proximosVencimento = cur.execute("""
            SELECT nome, data_validade, (
                SELECT quantidade FROM estoque WHERE produto_id = produtos.id
            ) AS quantidade
            FROM produtos
            WHERE ativo = 1 AND status_validade = 'próximo do vencimento'
            ORDER BY data_validade ASC
            LIMIT 5
        """).fetchall()

    # Exibir excesso de estoque
    elif modo == "excesso":
        excessos = cur.execute("""
            SELECT p.id, p.nome, p.codigo, p.categoria, e.quantidade
            FROM estoque e
            LEFT JOIN produtos p ON e.produto_id = p.id
            WHERE e.quantidade >= 100 AND p.ativo = 1
            ORDER BY e.quantidade DESC
        """).fetchall()

    conn.close()

    return render_template(
        "inicio/home.html",
        total_produtos=total_produtos,
        estoque_baixo=estoque_baixo,
        proximosVencimento=proximosVencimento,
        excessos=excessos,
        modo=modo,
        quase_vencidos=quase_vencidos,
        valor_total=float(valor_total),
        mais_vendidos=mais_vendidos
    )


@app.route("/gerenciamento")
@login_required
def gerenciamento():
    atualizar_produtos()

    conn = conectar()
    cur = conn.cursor()

    nome = request.args.get("nome", "").capitalize()
    categoria = request.args.get("categoria", "").capitalize()

    query = """
    Select p.id, p.nome, p.codigo, p.categoria, p.preco, p.data_validade, 
    p.status_validade, p.ativo, f.nome AS fornecedor
    From produtos p
    Left Join fornecedores f On p.fornecedor_id = f.id
    Where p.ativo = 1
    """
    params = []

    if nome:
        query += " And p.nome LIKE ?"
        params.append(f"%{nome}%")

    if categoria:
        query += " And p.categoria = ?"
        params.append(categoria)

    cur.execute(query, params)
    produtos = cur.fetchall()


    return render_template("gerencia/produtos.html", nome=nome, categoria=categoria, produtos=produtos)


@app.route("/cadastrar_produto", methods=["POST", "GET"])
@admin_required
def novo_produto():
    atualizar_produtos()
    
    conn = conectar()
    cur = conn.cursor()

    if request.method == "POST":
        nome = request.form["nome"].capitalize()
        descricao = request.form["descricao"]
        categoria = request.form["categoria"]
        data_validade = request.form["data_validade"]
        fornecedor_id = request.form["fornecedor_id"]
        preco = float(request.form["preco"])
        quantidade = int(request.form["quantidade"])

        cur.execute("""Insert Into produtos (nome, descricao, categoria, fornecedor_id, preco, data_validade)
            Values (?, ?, ?, ?, ?, ?)""", (nome, descricao, categoria, fornecedor_id, preco, data_validade))

        produto_id = cur.lastrowid

        #geração do código
        prefixo = categoria[:2].upper()
        codigo = f"{prefixo}{str(produto_id).zfill(3)}"

        cur.execute("Update produtos Set codigo=? Where id=?", (codigo, produto_id))
        cur.execute("Insert Into estoque (produto_id, quantidade) Values (?, ?)", (produto_id, quantidade))
        
        conn.commit()
        conn.close()

        return redirect(url_for("gerenciamento"))

    fornecedores = cur.execute("Select id, nome From fornecedores Where ativo=1").fetchall()
    conn.close()
    
    return render_template("gerencia/cadastrar.html", fornecedores=fornecedores)


@app.route("/editar/<int:id>", methods=["GET", "POST"])
@admin_required
def editar_produto(id):
    atualizar_produtos()

    conn = conectar()
    cur = conn.cursor()

    if request.method == "POST":
        nome = request.form["nome"]
        descricao = request.form["descricao"]
        categoria = request.form["categoria"]
        fornecedor_id = request.form["fornecedor"]
        preco = float(request.form["preco"])
        quantidade = int(request.form["quantidade"])

        cur.execute("Update produtos Set nome=?, descricao=?, categoria=?, fornecedor_id=?, preco=? Where id=?",
            (nome, descricao, categoria, fornecedor_id, preco, id),)

        cur.execute("Update estoque Set quantidade=?, atualizado_em=CURRENT_TIMESTAMP Where produto_id=?",
            (quantidade, id),)

        conn.commit()
        conn.close()

        return redirect(url_for("gerenciamento"))

    cur.execute("Select * From produtos Where id=?", (id,))
    produto = cur.fetchone()

    cur.execute("Select quantidade From estoque Where produto_id=?", (id,))
    estoque = cur.fetchone()
    
    fornecedores = cur.execute("Select id, nome From fornecedores Where ativo=1").fetchall()
    conn.close()

    return render_template("gerencia/editar.html", produto=produto, estoque=estoque, fornecedores=fornecedores)


@app.route("/inativar/<int:id>")
@admin_required
def inativar_produto(id):
    conn = conectar()
    cur = conn.cursor()
    
    cur.execute("Update produtos Set ativo = 0 Where id = ?", (id,))
    conn.commit()
    conn.close()
    
    return redirect(url_for("gerenciamento"))


@app.route("/movimentacoes", methods=["GET", "POST"])
@login_required
def movimentacao():
    atualizar_produtos()

    conn = conectar()
    cur = conn.cursor()

    movimentos = cur.execute("""
        SELECT m.id, m.tipo, m.quantidade, m.data, p.nome AS produto_nome 
        FROM movimentacoes m 
        LEFT JOIN produtos p ON m.produto_id = p.id 
        ORDER BY m.data DESC LIMIT 50
    """).fetchall()

    produtos = cur.execute("SELECT id, nome FROM produtos WHERE ativo=1").fetchall()

    if request.method == "POST":
        produto_id = int(request.form["produto_id"])
        quantidade = int(request.form["quantidade"])
        tipo = request.form["tipo"]

        cur.execute("SELECT quantidade FROM estoque WHERE produto_id=?", (produto_id,))
        atual = cur.fetchone()

        if not atual:
            conn.close()
            flash("Produto não encontrado no estoque!", "danger")
            return redirect(url_for("movimentacao"))

        quantidade_atual = atual[0]

        if tipo == "saida" and quantidade > quantidade_atual:
            conn.close()
            flash(f"Operação inválida! Estoque insuficiente ({quantidade_atual} unidades disponíveis).", "danger")
            return redirect(url_for("movimentacao"))

        if tipo == "entrada":
            cur.execute("""
                Update estoque 
                Set quantidade = quantidade + ?, atualizado_em = CURRENT_TIMESTAMP 
                Where produto_id=?
            """, (quantidade, produto_id))
        elif tipo == "saída":
            cur.execute("""
                Update estoque 
                Set quantidade = quantidade - ?, atualizado_em = CURRENT_TIMESTAMP 
                Where produto_id=?
            """, (quantidade, produto_id))

        cur.execute("""
            Insert Into movimentacoes (produto_id, tipo, quantidade) 
            Values (?, ?, ?)
        """, (produto_id, tipo, quantidade))

        conn.commit()
        conn.close()

        flash("Movimentação registrada com sucesso!", "success")
        return redirect(url_for("movimentacao"))

    conn.close()
    return render_template("outros/mov.html", produtos=produtos, movimentos=movimentos)

@app.route("/fornecedores", methods=["GET"])
@admin_required
def listar_forn():
    atualizar_produtos()

    conn = conectar()
    cur = conn.cursor()

    nome = request.args.get("nome", "").strip().capitalize()
    cnpj_cpf = request.args.get("cnpj_cpf", "").strip().capitalize()

    query = "Select * From fornecedores Where ativo=1"
    p = []

    if nome:
        query += " and nome like ?"
        p.append(f"%{nome}%")

    if cnpj_cpf:
        query += " And cnpj_cpf like ?"
        p.append(f"%{cnpj_cpf}%")

    query += " order by nome asc"

    cur.execute(query, p)
    fornecedores = cur.fetchall()
    conn.close()

    return render_template("forn/listar_forn.html", fornecedores=fornecedores, nome=nome, cnpj_cpf=cnpj_cpf)


@app.route("/fornecedores/novo", methods=["GET", "POST"])
@admin_required
def cadastrar_fornecedor():
    atualizar_produtos()

    conn = conectar()
    cur = conn.cursor()

    if request.method == "POST":
        nome = request.form["nome"]
        cnpj_cpf = request.form["cnpj_cpf"]
        telefone = request.form["telefone"]
        email = request.form["email"]

        cur.execute("Insert Into fornecedores (nome, cnpj_cpf, telefone, email) Values (?, ?, ?, ?)",
            (nome, cnpj_cpf, telefone, email),)

        conn.commit()
        conn.close()

        return redirect(url_for("listar_forn"))

    conn.close()
    
    return render_template("forn/cadastrar_forn.html")


@app.route("/fornecedores/inativar/<int:id>")
@admin_required
def inativar_fornecedor(id):
    conn = conectar()
    cur = conn.cursor()

    cur.execute("Update fornecedores Set ativo=0 Where id=?", (id,))
    conn.commit()
    conn.close()

    return redirect(url_for("listar_forn"))


@app.route('/fornecedores/editar/<int:id>', methods=["GET", "POST"])
@admin_required
def editar_fornecedor(id):
    atualizar_produtos()

    conn = conectar()
    cur = conn.cursor()

    if request.method == "POST":
        nome = request.form["nome"]
        cnpj_cpf = request.form['cnpj_cpf']
        telefone = request.form["telefone"]
        email = request.form["email"]

        cur.execute('Update fornecedores Set nome=?, cnpj_cpf=?, telefone=?, email=? Where id=?;',
        (nome, cnpj_cpf, telefone, email, id))
        
        conn.commit()
        conn.close()

        return redirect(url_for("listar_forn"))
    
    fornecedor = cur.execute('SELECT * FROM fornecedores WHERE id=?', (id,)).fetchone()
    conn.close()
    return render_template('forn/editar_forn.html', fornecedor=fornecedor)

@app.route("/usuarios")
@admin_required
def listar_usuarios():
    atualizar_produtos()

    conn = conectar()
    cur = conn.cursor()

    cur.execute("SELECT id, nome, usuario, perfil, CAST(ativo AS INTEGER) FROM usuarios ORDER BY id ASC")
    usuarios = cur.fetchall()
    conn.close()

    return render_template("usuarios/listar.html", usuarios=usuarios)


@app.route("/usuarios/novo", methods=["GET", "POST"])
@admin_required
def cadastrar_usuario():
    atualizar_produtos()

    conn = conectar()
    cur = conn.cursor()

    if request.method == "POST":
        nome = request.form["nome"]
        usuario = request.form["usuario"]
        senha = generate_password_hash(request.form["senha"])
        perfil = "operador" 
        ativo = 1

        cur.execute("SELECT id FROM usuarios WHERE usuario = ?", (usuario,))
        existente = cur.fetchone()
        
        if existente:
            flash("Esse nome de usuário já está sendo usado.")
            conn.close()
            return redirect(url_for("novo_usuario"))

        cur.execute("""INSERT INTO usuarios (nome, usuario, senha, perfil, ativo)
            VALUES (?, ?, ?, ?, ?)""", (nome, usuario, senha, perfil, ativo))

        conn.commit()
        conn.close()
        flash("Operador criado com sucesso!")
        return redirect(url_for("listar_usuarios"))

    conn.close()
    return render_template("usuarios/novo.html")

@app.route("/usuarios/inativar/<int:id>")
@admin_required
def inativar_usuario(id):
    conn = conectar()
    cur = conn.cursor()

    cur.execute("UPDATE usuarios SET ativo = 0 WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash("Usuário inativado com sucesso!")

    return redirect(url_for("listar_usuarios"))

@app.route("/usuarios/editar/<int:id>", methods=["GET", "POST"])
@admin_required
def editar_usuario(id):
    atualizar_produtos()

    conn = conectar()
    cur = conn.cursor()

    if request.method == "POST":
        nome = request.form["nome"]
        usuario = request.form["usuario"]
        perfil = request.form["perfil"]

        cur.execute("""UPDATE usuarios SET nome=?, usuario=?, perfil=? WHERE id=?""", (nome, usuario, perfil, id))

        conn.commit()
        conn.close()
        flash("Usuário atualizado com sucesso!", "success")
        return redirect(url_for("listar_usuarios"))

    usuario = cur.execute("SELECT * FROM usuarios WHERE id=?", (id,)).fetchone()
    conn.close()

    return render_template("usuarios/editar.html", usuario=usuario)

@app.route("/relatorios", methods=["GET", "POST"])
@login_required
def relatorios():
    atualizar_produtos()

    conn = conectar()
    cur = conn.cursor()

    tipo_exportar = request.args.get("exportar")

    if tipo_exportar == "csv":
        registros = cur.execute("""
            SELECT m.id, p.nome AS produto, m.tipo, m.quantidade, m.data
            FROM movimentacoes m
            LEFT JOIN produtos p ON m.produto_id = p.id
            ORDER BY m.data DESC LIMIT 100
        """).fetchall()

        conn.close()

        import io, csv 
        from datetime import date

        output = io.StringIO()
        output.write(f"Relatório de Movimentações - Data: {date.today()}\n\n")
        writer = csv.writer(output, delimiter=";", quotechar='"', quoting=csv.QUOTE_MINIMAL)
        writer.writerow(["ID", "Produto", "Tipo", "Quantidade", "Data"])

        for linha in registros:
            writer.writerow(linha)

        nome_arquivo = f"relatorio_GEC_{date.today().strftime('%d-%m-%Y')}.csv"

        from flask import Response
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename={nome_arquivo}"}
        )

    if tipo_exportar == "pdf":
        registros = cur.execute("""
            SELECT m.id, p.nome AS produto, m.tipo, m.quantidade, m.data
            FROM movimentacoes m
            LEFT JOIN produtos p ON m.produto_id = p.id
            ORDER BY m.data DESC LIMIT 100
        """).fetchall()

        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        from reportlab.lib import colors
        from io import BytesIO
        from datetime import date

        buffer = BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4

        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawString(50, height - 50, "Relatório de Movimentações")
        pdf.setFont("Helvetica", 12)
        pdf.drawString(50, height - 70, f"Data: {date.today().strftime('%d/%m/%Y')}")

        y = height - 110

        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(50, y, "ID")
        pdf.drawString(100, y, "Produto")
        pdf.drawString(260, y, "Tipo")
        pdf.drawString(330, y, "Qtd")
        pdf.drawString(380, y, "Data")

        y -= 20
        pdf.setFont("Helvetica", 10)

        for r in registros:
            if y < 50:
                pdf.showPage()
                y = height - 50

            pdf.drawString(50, y, str(r[0]))
            pdf.drawString(100, y, str(r[1]))
            pdf.drawString(260, y, str(r[2]))
            pdf.drawString(330, y, str(r[3]))
            pdf.drawString(380, y, str(r[4]))
            y -= 18

        pdf.save()
        buffer.seek(0)

        nome_pdf = f"relatorio_GEC_{date.today().strftime('%d-%m-%Y')}.pdf"

        from flask import send_file
        return send_file(
            buffer,
            as_attachment=True,
            download_name=nome_pdf,
            mimetype="application/pdf"
        )

    # estoque atual
    estoque_atual = cur.execute("""
        SELECT p.id, p.nome, p.codigo, p.categoria, e.quantidade
        FROM estoque e
        LEFT JOIN produtos p ON e.produto_id = p.id
        WHERE p.ativo=1
        ORDER BY p.nome ASC
    """).fetchall()

    # estoque baixo
    estoque_baixo = cur.execute("""
        SELECT p.id, p.nome, p.codigo, p.categoria, e.quantidade
        FROM estoque e
        LEFT JOIN produtos p ON e.produto_id = p.id
        WHERE p.ativo=1 AND e.quantidade <= 20
        ORDER BY e.quantidade ASC
    """).fetchall()

    movimentos = []
    if request.method == "POST":
        data_inicio = request.form["data_inicio"]
        data_fim = request.form["data_fim"]

        movimentos = cur.execute("""
            SELECT m.id, m.tipo, m.quantidade, m.data, p.nome
            FROM movimentacoes m
            LEFT JOIN produtos p ON m.produto_id = p.id
            WHERE date(m.data) BETWEEN date(?) AND date(?)
            ORDER BY m.data DESC
        """, (data_inicio, data_fim)).fetchall()
    else:
        movimentos = cur.execute("""
            SELECT m.id, m.tipo, m.quantidade, m.data, p.nome
            FROM movimentacoes m
            LEFT JOIN produtos p ON m.produto_id = p.id
            ORDER BY m.data DESC LIMIT 15
        """).fetchall()

    conn.close()

    return render_template(
        "outros/relatorio.html",
        estoque_atual=estoque_atual,
        estoque_baixo=estoque_baixo,
        movimentos=movimentos
)

if __name__ == "__main__":
    app.run(debug=True)