import sqlite3

def conectar():
    return sqlite3.connect("data/estoque.db")


conn = conectar()
cur = conn.cursor()

#tabelas: usuarios, produtos, fornecedores, movimentações, auditoria

cur.execute('''
CREATE TABLE IF NOT EXISTS "usuarios" (
	"id"	INTEGER,
	"nome"	TEXT NOT NULL,
	"usuario"	TEXT NOT NULL,
	"senha"	TEXT NOT NULL,
	"perfil"	TEXT NOT NULL DEFAULT 'operador',
    "ativo" TEXT NOT NULL DEFAULT 1,
	PRIMARY KEY("id" AUTOINCREMENT)
)
''')

cur.execute('''
    CREATE TABLE IF NOT EXISTS "fornecedores" (
	"id"	INTEGER,
	"nome"	TEXT NOT NULL,
	"cnpj_cpf"	TEXT NOT NULL,
	"telefone"	TEXT NOT NULL,
	"email"	TEXT NOT NULL,
	PRIMARY KEY("id" AUTOINCREMENT)
)
''')


cur.execute('''
	CREATE TABLE IF NOT EXISTS "produtos" (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    descricao TEXT,
    codigo TEXT UNIQUE NOT NULL,
    categoria TEXT,
    preco REAL NOT NULL,
    fornecedor_id INTEGER,
	data_validade TEXT NOT NULL,
    ativo INTEGER DEFAULT 1,
    FOREIGN KEY(fornecedor_id) REFERENCES fornecedores(id)
)
''')

cur.execute('''
	CREATE TABLE IF NOT EXISTS "estoque" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "produto_id" INTEGER NOT NULL,
    "quantidade" INTEGER DEFAULT 0,
	"atualizado_em" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(produto_id) REFERENCES produtos(id)
)
''')

cur.execute('''
    CREATE TABLE IF NOT EXISTS movimentacoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    produto_id INTEGER,
    tipo TEXT,
    quantidade INTEGER,
    data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)''')

conn.commit()
conn.close()