# app.py
# SGIONGs - Plataforma de filtragem de ONGs/OSCs (Gaza)
# Flask + SQLite + Bootstrap 5

import math
import os
import secrets
import time
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session

from database import get_connection, init_db
from tagging import detetar_distritos, detetar_areas, detetar_ramificacoes, PROVINCIAS, AREAS_TEMATICAS, ESTRUTURA_AREAS_TEMATICAS
from config import ADMIN_USERNAME, ADMIN_PASSWORD, SUPER_ADMIN_USERNAME, SUPER_ADMIN_PASSWORD

app = Flask(__name__)

# A secret_key assina as sessões de login. Em vez de um texto fixo no código
# (que seria igual em todas as instalações do SGIONGs, e portanto previsível),
# geramos uma chave aleatória única na primeira vez que a app corre, e
# guardamo-la num ficheiro local para se manter estável entre reinícios.
_CAMINHO_CHAVE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.chave_secreta')
if not os.path.exists(_CAMINHO_CHAVE):
    with open(_CAMINHO_CHAVE, 'w') as f:
        f.write(secrets.token_hex(32))
with open(_CAMINHO_CHAVE) as f:
    app.secret_key = f.read().strip()

POR_PAGINA = 12



# ─── FUNÇÕES DE SESSÃO ────────────────────────────────────────────────────────
def nivel_sessao():
    """Devolve o nível do utilizador autenticado: 'superadmin', 'admin' ou None."""
    return session.get('nivel')

def e_admin():
    return nivel_sessao() in ('admin', 'superadmin')

def e_super_admin():
    return nivel_sessao() == 'superadmin'


# ─── DECORATORS ───────────────────────────────────────────────────────────────
def login_obrigatorio(f):
    """Permite acesso a qualquer utilizador autenticado (admin ou superadmin)."""
    @wraps(f)
    def decorada(*args, **kwargs):
        if not e_admin():
            flash('Precisa de iniciar sessão para fazer essa ação.', 'warning')
            destino = request.path if request.method == 'GET' else (request.referrer or url_for('inicio'))
            return redirect(url_for('login', next=destino))
        return f(*args, **kwargs)
    return decorada


def super_admin_obrigatorio(f):
    """Permite acesso apenas ao Super Administrador."""
    @wraps(f)
    def decorada(*args, **kwargs):
        if not e_super_admin():
            flash('Esta ação requer permissão de Super Administrador.', 'danger')
            return redirect(url_for('inicio'))
        return f(*args, **kwargs)
    return decorada


# ─── PROTEÇÃO CONTRA FORÇA BRUTA ──────────────────────────────────────────────
_tentativas_login = {}
LIMITE_TENTATIVAS_LOGIN = 5
JANELA_TENTATIVAS_SEGUNDOS = 300


def _ip_com_demasiadas_tentativas(ip):
    agora = time.time()
    recentes = [t for t in _tentativas_login.get(ip, []) if agora - t < JANELA_TENTATIVAS_SEGUNDOS]
    _tentativas_login[ip] = recentes
    return len(recentes) >= LIMITE_TENTATIVAS_LOGIN


def _registar_tentativa_falhada(ip):
    _tentativas_login.setdefault(ip, []).append(time.time())


# ─── ROTAS DE AUTENTICAÇÃO ────────────────────────────────────────────────────
@app.route('/login', methods=['GET', 'POST'])
def login():
    if e_admin():
        return redirect(url_for('inicio'))
    if request.method == 'POST':
        ip = request.remote_addr
        if _ip_com_demasiadas_tentativas(ip):
            flash('Demasiadas tentativas falhadas. Aguarde alguns minutos.', 'danger')
            return render_template('login.html', next=request.args.get('next', ''))
        utilizador = request.form.get('utilizador', '').strip()
        senha = request.form.get('senha', '')
        if utilizador == SUPER_ADMIN_USERNAME and senha == SUPER_ADMIN_PASSWORD:
            session['nivel'] = 'superadmin'
            flash('Sessão de Super Administrador iniciada.', 'success')
        elif utilizador == ADMIN_USERNAME and senha == ADMIN_PASSWORD:
            session['nivel'] = 'admin'
            flash('Sessão de Administrador iniciada.', 'success')
        else:
            _registar_tentativa_falhada(ip)
            flash('Utilizador ou senha incorretos.', 'danger')
            return render_template('login.html', next=request.args.get('next', ''))
        destino = request.args.get('next') or request.form.get('next')
        if not destino or not destino.startswith('/'):
            destino = url_for('inicio')
        return redirect(destino)
    return render_template('login.html', next=request.args.get('next', ''))


@app.route('/logout')
def logout():
    session.pop('nivel', None)
    flash('Sessão terminada.', 'info')
    return redirect(url_for('inicio'))


@app.before_request
def garantir_bd():
    init_db()


def obter_ou_criar_id(conn, tabela, nome):
    cur = conn.execute(f'SELECT id FROM {tabela} WHERE nome = ?', (nome,))
    linha = cur.fetchone()
    if linha:
        return linha['id']
    cur = conn.execute(f'INSERT INTO {tabela} (nome) VALUES (?)', (nome,))
    return cur.lastrowid


def obter_ou_criar_ramificacao_id(conn, nome, area_id):
    cur = conn.execute('SELECT id FROM ramificacoes WHERE nome = ?', (nome,))
    linha = cur.fetchone()
    if linha:
        return linha['id']
    cur = conn.execute('INSERT INTO ramificacoes (nome, area_id) VALUES (?, ?)', (nome, area_id))
    return cur.lastrowid


SUB_PARA_AREA = {sub: area for area, subs in ESTRUTURA_AREAS_TEMATICAS.items() for sub in subs}


def sincronizar_tags(conn, ong_id, distritos_texto, area_texto, provincia=None):
    conn.execute('DELETE FROM ong_distritos WHERE ong_id = ?', (ong_id,))
    conn.execute('DELETE FROM ong_areas WHERE ong_id = ?', (ong_id,))
    conn.execute('DELETE FROM ong_ramificacoes WHERE ong_id = ?', (ong_id,))
    for distrito in detetar_distritos(distritos_texto, provincia):
        distrito_id = obter_ou_criar_id(conn, 'distritos', distrito)
        conn.execute('INSERT OR IGNORE INTO ong_distritos (ong_id, distrito_id) VALUES (?, ?)',
                     (ong_id, distrito_id))
    for area in detetar_areas(area_texto):
        area_id = obter_ou_criar_id(conn, 'areas', area)
        conn.execute('INSERT OR IGNORE INTO ong_areas (ong_id, area_id) VALUES (?, ?)',
                     (ong_id, area_id))
    for ramificacao in detetar_ramificacoes(area_texto):
        area_da_ramificacao = SUB_PARA_AREA.get(ramificacao)
        if not area_da_ramificacao:
            continue
        area_id = obter_ou_criar_id(conn, 'areas', area_da_ramificacao)
        ramificacao_id = obter_ou_criar_ramificacao_id(conn, ramificacao, area_id)
        conn.execute('INSERT OR IGNORE INTO ong_ramificacoes (ong_id, ramificacao_id) VALUES (?, ?)',
                     (ong_id, ramificacao_id))


def obter_listas_filtro(conn, provincia=None, area_id=None):
    if provincia:
        distritos = conn.execute(
            'SELECT id, nome FROM distritos WHERE provincia = ? ORDER BY nome', (provincia,)
        ).fetchall()
    else:
        distritos = conn.execute('SELECT id, nome FROM distritos ORDER BY nome').fetchall()
    areas = conn.execute('SELECT id, nome FROM areas ORDER BY nome').fetchall()
    if area_id:
        ramificacoes = conn.execute(
            'SELECT id, nome FROM ramificacoes WHERE area_id = ? ORDER BY nome', (area_id,)
        ).fetchall()
    else:
        ramificacoes = conn.execute('SELECT id, nome FROM ramificacoes ORDER BY nome').fetchall()
    return distritos, areas, ramificacoes


@app.route('/')
def inicio():
    conn = get_connection()

    total_ongs = conn.execute("SELECT COUNT(*) c FROM ongs WHERE aprovacao='Aprovado'").fetchone()['c']
    total_provincias = conn.execute(
        "SELECT COUNT(DISTINCT provincia) c FROM ongs WHERE provincia IS NOT NULL AND provincia != ''"
    ).fetchone()['c']
    total_distritos = conn.execute('SELECT COUNT(DISTINCT distrito_id) c FROM ong_distritos').fetchone()['c']
    total_areas = conn.execute('SELECT COUNT(DISTINCT area_id) c FROM ong_areas').fetchone()['c']

    por_provincia = conn.execute('''
        SELECT provincia, COUNT(*) c FROM ongs
        WHERE provincia IS NOT NULL AND provincia != ''
        GROUP BY provincia ORDER BY c DESC
    ''').fetchall()

    recentes = conn.execute('''
        SELECT id, nome, provincia, natureza, criado_em FROM ongs
        ORDER BY criado_em DESC LIMIT 5
    ''').fetchall()

    conn.close()
    return render_template('inicio.html',
                            total_ongs=total_ongs,
                            total_provincias=total_provincias,
                            total_distritos=total_distritos,
                            total_areas=total_areas,
                            por_provincia=por_provincia,
                            recentes=recentes)


@app.route('/ongs')
def index():
    conn = get_connection()

    q = request.args.get('q', '').strip()
    origem = request.args.get('origem', '').strip()
    natureza = request.args.get('natureza', '').strip()
    estado = request.args.get('estado', '').strip()
    provincia = request.args.get('provincia', '').strip()
    distrito_id = request.args.get('distrito_id', '').strip()
    area_id = request.args.get('area_id', '').strip()
    ramificacao_id = request.args.get('ramificacao_id', '').strip()
    pagina = max(1, request.args.get('pagina', 1, type=int))

    condicoes = []
    parametros = []
    joins = ''

    if q:
        condicoes.append('o.nome LIKE ?')
        parametros.append(f'%{q}%')
    if origem:
        condicoes.append('o.origem = ?')
        parametros.append(origem)
    if natureza:
        condicoes.append('o.natureza LIKE ?')
        parametros.append(f'%{natureza}%')
    if estado:
        condicoes.append('o.estado = ?')
        parametros.append(estado)
    if provincia:
        condicoes.append('o.provincia = ?')
        parametros.append(provincia)
    if distrito_id:
        joins += ' JOIN ong_distritos od ON od.ong_id = o.id '
        condicoes.append('od.distrito_id = ?')
        parametros.append(distrito_id)
    if area_id:
        joins += ' JOIN ong_areas oa ON oa.ong_id = o.id '
        condicoes.append('oa.area_id = ?')
        parametros.append(area_id)
    if ramificacao_id:
        joins += ' JOIN ong_ramificacoes orf ON orf.ong_id = o.id '
        condicoes.append('orf.ramificacao_id = ?')
        parametros.append(ramificacao_id)

    # Filtro de aprovação:
    # Visitantes e admins normais só veem ONGs aprovadas.
    # O Super Admin pode ver também as pendentes/rejeitadas (com filtro opcional).
    aprovacao_filtro = request.args.get('aprovacao', '').strip()
    if e_super_admin() and aprovacao_filtro:
        condicoes.append('o.aprovacao = ?')
        parametros.append(aprovacao_filtro)
    elif not e_super_admin():
        condicoes.append("o.aprovacao = 'Aprovado'")

    where = f"WHERE {' AND '.join(condicoes)}" if condicoes else ''

    total = conn.execute(
        f'SELECT COUNT(DISTINCT o.id) AS total FROM ongs o {joins} {where}', parametros
    ).fetchone()['total']
    total_paginas = max(1, math.ceil(total / POR_PAGINA))
    pagina = min(pagina, total_paginas)
    offset = (pagina - 1) * POR_PAGINA

    ongs = conn.execute(f'''
        SELECT DISTINCT o.* FROM ongs o {joins} {where}
        ORDER BY o.nome
        LIMIT ? OFFSET ?
    ''', parametros + [POR_PAGINA, offset]).fetchall()

    distritos_para_ongs = {}
    if ongs:
        ids = [str(o['id']) for o in ongs]
        linhas = conn.execute(f'''
            SELECT od.ong_id, d.nome FROM ong_distritos od
            JOIN distritos d ON d.id = od.distrito_id
            WHERE od.ong_id IN ({",".join(ids)})
        ''').fetchall()
        for linha in linhas:
            distritos_para_ongs.setdefault(linha['ong_id'], []).append(linha['nome'])

    distritos, areas, ramificacoes = obter_listas_filtro(conn, provincia, area_id)
    conn.close()

    return render_template('index.html',
                            ongs=ongs,
                            distritos_para_ongs=distritos_para_ongs,
                            distritos=distritos,
                            areas=areas,
                            ramificacoes=ramificacoes,
                            provincias=PROVINCIAS,
                            total=total,
                            pagina=pagina,
                            total_paginas=total_paginas,
                            filtros={'q': q, 'origem': origem, 'natureza': natureza, 'estado': estado, 'provincia': provincia,
                                     'distrito_id': distrito_id, 'area_id': area_id, 'ramificacao_id': ramificacao_id})


@app.route('/organizacoes')
def organizacoes():
    conn = get_connection()

    q = request.args.get('q', '').strip()
    provincia_filtro = request.args.get('provincia', '').strip()
    area_filtro = request.args.get('area', '').strip()
    ramificacao_filtro = request.args.get('ramificacao', '').strip()
    pagina = max(1, request.args.get('pagina', 1, type=int))

    linhas = conn.execute('SELECT id, nome, natureza, origem, provincia, estado FROM ongs').fetchall()

    # Pré-carregar distritos, áreas e ramificações de TODAS as ONGs de uma vez
    # (em vez de uma query por organização), para podermos filtrar antes de paginar.
    distritos_por_ong = {}
    for r in conn.execute('''
        SELECT od.ong_id, d.nome FROM ong_distritos od JOIN distritos d ON d.id = od.distrito_id
    '''):
        distritos_por_ong.setdefault(r['ong_id'], set()).add(r['nome'])

    areas_por_ong = {}
    for r in conn.execute('''
        SELECT oa.ong_id, a.nome FROM ong_areas oa JOIN areas a ON a.id = oa.area_id
    '''):
        areas_por_ong.setdefault(r['ong_id'], set()).add(r['nome'])

    ramificacoes_por_ong = {}
    for r in conn.execute('''
        SELECT orf.ong_id, r.nome FROM ong_ramificacoes orf JOIN ramificacoes r ON r.id = orf.ramificacao_id
    '''):
        ramificacoes_por_ong.setdefault(r['ong_id'], set()).add(r['nome'])

    # Agrupar por nome (normalizado), juntando as provincias/naturezas/origens/
    # distritos/areas/ramificacoes de cada linha que pertence à mesma organização.
    grupos = {}
    for r in linhas:
        chave = r['nome'].strip().lower()
        grupo = grupos.setdefault(chave, {
            'nome': r['nome'].strip(), 'ids': [], 'provincias': set(),
            'naturezas': set(), 'origens': set(), 'estados': set(),
            'distritos': set(), 'areas': set(), 'ramificacoes': set(),
        })
        grupo['ids'].append(r['id'])
        if r['provincia']:
            grupo['provincias'].add(r['provincia'])
        if r['natureza']:
            for n in r['natureza'].split(','):
                grupo['naturezas'].add(n.strip())
        if r['origem']:
            grupo['origens'].add(r['origem'])
        if r['estado']:
            grupo['estados'].add(r['estado'])
        grupo['distritos'] |= distritos_por_ong.get(r['id'], set())
        grupo['areas'] |= areas_por_ong.get(r['id'], set())
        grupo['ramificacoes'] |= ramificacoes_por_ong.get(r['id'], set())

    lista = list(grupos.values())

    if q:
        q_lower = q.lower()
        lista = [g for g in lista if q_lower in g['nome'].lower()]
    if provincia_filtro:
        lista = [g for g in lista if provincia_filtro in g['provincias']]
    if area_filtro:
        lista = [g for g in lista if area_filtro in g['areas']]
    if ramificacao_filtro:
        lista = [g for g in lista if ramificacao_filtro in g['ramificacoes']]

    lista.sort(key=lambda g: g['nome'].lower())

    total = len(lista)
    total_paginas = max(1, math.ceil(total / POR_PAGINA))
    pagina = min(pagina, total_paginas)
    pagina_lista = lista[(pagina - 1) * POR_PAGINA: pagina * POR_PAGINA]

    organizacoes_pagina = [{
        'nome': g['nome'],
        'ids': g['ids'],
        'num_registos': len(g['ids']),
        'provincias': sorted(g['provincias']),
        'distritos': sorted(g['distritos']),
        'areas': sorted(g['areas']),
        'ramificacoes': sorted(g['ramificacoes']),
        'naturezas': sorted(g['naturezas']),
        'origens': sorted(g['origens']),
        'estados': sorted(g['estados']),
    } for g in pagina_lista]

    ramificacoes_da_area = list(ESTRUTURA_AREAS_TEMATICAS[area_filtro]) if area_filtro in ESTRUTURA_AREAS_TEMATICAS else []

    conn.close()
    return render_template('organizacoes.html',
                            organizacoes=organizacoes_pagina,
                            provincias=PROVINCIAS,
                            areas_tematicas=AREAS_TEMATICAS,
                            ramificacoes_da_area=ramificacoes_da_area,
                            total=total,
                            pagina=pagina,
                            total_paginas=total_paginas,
                            filtros={'q': q, 'provincia': provincia_filtro, 'area': area_filtro,
                                     'ramificacao': ramificacao_filtro})


@app.route('/dashboard')
def dashboard():
    conn = get_connection()

    provincia_filtro = request.args.get('provincia', '').strip()
    distrito_id_filtro = request.args.get('distrito_id', '').strip()

    # Subconjunto de ONGs que respeita os filtros atuais (provincia e/ou distrito).
    # Construído uma vez e reutilizado em todas as queries de agregação abaixo,
    # para evitar repetir lógica de WHERE/JOIN espalhada pelo código.
    condicoes = []
    params_sub = []
    join_distrito = ''
    if provincia_filtro:
        condicoes.append('o.provincia = ?')
        params_sub.append(provincia_filtro)
    if distrito_id_filtro:
        join_distrito = 'JOIN ong_distritos od_f ON od_f.ong_id = o.id'
        condicoes.append('od_f.distrito_id = ?')
        params_sub.append(distrito_id_filtro)
    where_sub = f"WHERE {' AND '.join(condicoes)}" if condicoes else ''
    subquery_ids = f'(SELECT DISTINCT o.id FROM ongs o {join_distrito} {where_sub})'

    distritos_filtro, _, _ = obter_listas_filtro(conn, provincia_filtro)
    nome_distrito_filtro = None
    if distrito_id_filtro:
        linha = conn.execute('SELECT nome FROM distritos WHERE id = ?', (distrito_id_filtro,)).fetchone()
        nome_distrito_filtro = linha['nome'] if linha else None

    total_ongs = conn.execute(f'SELECT COUNT(*) c FROM ongs WHERE id IN {subquery_ids}', params_sub).fetchone()['c']

    total_provincias = 1 if provincia_filtro else conn.execute(
        "SELECT COUNT(DISTINCT provincia) c FROM ongs WHERE provincia IS NOT NULL AND provincia != ''"
    ).fetchone()['c']

    if distrito_id_filtro:
        total_distritos = 1
    else:
        total_distritos = conn.execute(f'''
            SELECT COUNT(DISTINCT distrito_id) c FROM ong_distritos WHERE ong_id IN {subquery_ids}
        ''', params_sub).fetchone()['c']

    total_areas = conn.execute(f'''
        SELECT COUNT(DISTINCT area_id) c FROM ong_areas WHERE ong_id IN {subquery_ids}
    ''', params_sub).fetchone()['c']

    por_provincia = conn.execute('''
        SELECT provincia, COUNT(*) c FROM ongs
        WHERE provincia IS NOT NULL AND provincia != ''
        GROUP BY provincia ORDER BY c DESC
    ''').fetchall()

    por_area = conn.execute(f'''
        SELECT a.nome, COUNT(*) c FROM ong_areas oa
        JOIN areas a ON a.id = oa.area_id
        WHERE oa.ong_id IN {subquery_ids}
        GROUP BY a.nome ORDER BY c DESC
    ''', params_sub).fetchall()

    por_origem = conn.execute(f'''
        SELECT origem, COUNT(*) c FROM ongs
        WHERE id IN {subquery_ids} AND origem IS NOT NULL AND origem != ''
        GROUP BY origem ORDER BY c DESC
    ''', params_sub).fetchall()

    por_estado = conn.execute(f'''
        SELECT estado, COUNT(*) c FROM ongs WHERE id IN {subquery_ids} GROUP BY estado ORDER BY c DESC
    ''', params_sub).fetchall()

    natureza_contagens = {
        'ONG': conn.execute(f"SELECT COUNT(*) c FROM ongs WHERE id IN {subquery_ids} AND natureza LIKE '%ONG%'", params_sub).fetchone()['c'],
        'OSC': conn.execute(f"SELECT COUNT(*) c FROM ongs WHERE id IN {subquery_ids} AND natureza LIKE '%OSC%'", params_sub).fetchone()['c'],
        'Fundação': conn.execute(f"SELECT COUNT(*) c FROM ongs WHERE id IN {subquery_ids} AND natureza LIKE '%Fundação%'", params_sub).fetchone()['c'],
    }

    # Ramificações: para cada área temática, contamos quantas ONGs mencionam
    # cada uma das suas ramificações (sub-categorias) oficiais. As ramificações
    # sem nenhuma ONG aparecem com 0 (em vez de desaparecerem), e a ordem
    # segue sempre a taxonomia oficial, não a contagem.
    sub_para_area = {sub: area for area, subs in ESTRUTURA_AREAS_TEMATICAS.items() for sub in subs}

    textos = conn.execute(f'''
        SELECT area_intervencao FROM ongs WHERE id IN {subquery_ids} AND area_intervencao IS NOT NULL
    ''', params_sub).fetchall()

    contagem_ramificacoes = {area: {sub: 0 for sub in subs} for area, subs in ESTRUTURA_AREAS_TEMATICAS.items()}
    for linha in textos:
        for sub in detetar_ramificacoes(linha['area_intervencao']):
            contagem_ramificacoes[sub_para_area[sub]][sub] += 1

    total_ongs_por_area = {r['nome']: r['c'] for r in por_area}

    ramificacoes = {
        area: [(sub, contagem_ramificacoes[area][sub]) for sub in ESTRUTURA_AREAS_TEMATICAS[area]]
        for area in ESTRUTURA_AREAS_TEMATICAS
    }

    conn.close()

    return render_template('dashboard.html',
                            provincias=PROVINCIAS,
                            provincia_filtro=provincia_filtro,
                            distritos_filtro=distritos_filtro,
                            distrito_id_filtro=distrito_id_filtro,
                            nome_distrito_filtro=nome_distrito_filtro,
                            total_ongs=total_ongs,
                            total_provincias=total_provincias,
                            total_distritos=total_distritos,
                            total_areas=total_areas,
                            provincia_labels=[r['provincia'] for r in por_provincia],
                            provincia_valores=[r['c'] for r in por_provincia],
                            area_labels=[r['nome'] for r in por_area],
                            area_valores=[r['c'] for r in por_area],
                            origem_labels=[r['origem'] for r in por_origem],
                            origem_valores=[r['c'] for r in por_origem],
                            estado_labels=[r['estado'] for r in por_estado],
                            estado_valores=[r['c'] for r in por_estado],
                            natureza_labels=list(natureza_contagens.keys()),
                            natureza_valores=list(natureza_contagens.values()),
                            ramificacoes=ramificacoes,
                            total_ongs_por_area=total_ongs_por_area)


@app.route('/levantamento-nacional')
def levantamento_nacional():
    """Resumo do levantamento nacional de ONGs/OSCs/Fundações feito pelo MPD
    (Ministério da Planificação e Desenvolvimento), com base na apresentação
    'Levantamento de ONG's que Operam no País' (Maputo, 29 de Abril de 2026).
    Os números aqui são fixos (vêm da apresentação, não da base de dados do
    SGIONGs) e servem como contexto nacional complementar à listagem interna.
    """
    natureza_labels = ['ONGs', 'OSCs/Associações', 'Fundações']
    natureza_valores = [580, 169, 52]

    origem_labels = ['Estrangeiras/Internacionais', 'Nacionais']
    origem_valores = [318, 176]

    provincia_labels = ['Maputo', 'Cabo Delgado', 'Sofala', 'Niassa', 'Gaza',
                         'Zambézia', 'Inhambane', 'Nampula', 'Manica', 'Tete']
    provincia_valores = [235, 131, 81, 75, 74, 55, 57, 34, 31, 28]

    sector_labels = ['Saúde', 'Agricultura e Segurança Alimentar', 'Educação',
                      'Acção Social', 'Outras', 'Conservação e Meio Ambiente',
                      'Infraestruturas', 'Ajuda Humanitária',
                      'Resiliência e Mudanças Climáticas', 'Pecuária']
    sector_valores = [226, 218, 109, 109, 66, 76, 59, 55, 6, 2]

    constatacoes = [
        'Das três categorias de actores locais analisadas, as ONGs são as mais numerosas, '
        'seguidas pelas Organizações da Sociedade Civil/Associações e, por último, pelas Fundações.',
        'A maior parte das ONGs identificadas é de origem estrangeira e está espalhada por '
        'praticamente todo o país.',
        'Maputo, Cabo Delgado e Sofala são as províncias com maior concentração de ONGs.',
        'Agricultura, Saúde e Educação são os sectores de actividade mais frequentes entre '
        'as organizações mapeadas.',
        'Cabo Delgado destaca-se pelo maior número de projectos de infra-estruturas sanitárias, '
        'escolares e agrárias, de reassentamento, de assistência a vítimas de eventos climáticos '
        'extremos e de ajuda humanitária.',
    ]

    return render_template('levantamento.html',
                            natureza_labels=natureza_labels,
                            natureza_valores=natureza_valores,
                            origem_labels=origem_labels,
                            origem_valores=origem_valores,
                            provincia_labels=provincia_labels,
                            provincia_valores=provincia_valores,
                            sector_labels=sector_labels,
                            sector_valores=sector_valores,
                            constatacoes=constatacoes,
                            total_geral=sum(natureza_valores))


@app.route('/pendentes')
@super_admin_obrigatorio
def pendentes():
    conn = get_connection()
    ongs_pendentes = conn.execute('''
        SELECT * FROM ongs WHERE aprovacao = 'Pendente' ORDER BY criado_em DESC
    ''').fetchall()
    conn.close()
    return render_template('pendentes.html', ongs=ongs_pendentes)


@app.route('/ong/<int:ong_id>/aprovar', methods=['POST'])
@super_admin_obrigatorio
def aprovar(ong_id):
    from datetime import datetime
    conn = get_connection()
    conn.execute('''
        UPDATE ongs SET aprovacao='Aprovado', aprovado_por=?, aprovado_em=?, motivo_rejeicao=NULL
        WHERE id=?
    ''', (SUPER_ADMIN_USERNAME, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), ong_id))
    conn.commit()
    conn.close()
    flash('ONG aprovada com sucesso.', 'success')
    return redirect(request.referrer or url_for('pendentes'))


@app.route('/ong/<int:ong_id>/rejeitar', methods=['POST'])
@super_admin_obrigatorio
def rejeitar(ong_id):
    from datetime import datetime
    motivo = request.form.get('motivo', '').strip() or 'Sem motivo indicado'
    conn = get_connection()
    conn.execute('''
        UPDATE ongs SET aprovacao='Rejeitado', aprovado_por=?, aprovado_em=?, motivo_rejeicao=?
        WHERE id=?
    ''', (SUPER_ADMIN_USERNAME, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), motivo, ong_id))
    conn.commit()
    conn.close()
    flash(f'ONG rejeitada. Motivo: {motivo}', 'danger')
    return redirect(request.referrer or url_for('pendentes'))


@app.route('/sector/<path:nome_area>')
def sector(nome_area):
    if nome_area not in ESTRUTURA_AREAS_TEMATICAS:
        flash(f'Área temática "{nome_area}" não encontrada.', 'warning')
        return redirect(url_for('dashboard'))

    conn = get_connection()

    provincia_filtro = request.args.get('provincia', '').strip()
    params_prov = [provincia_filtro] if provincia_filtro else []
    cond_prov = 'AND o.provincia = ?' if provincia_filtro else ''

    ramificacoes_da_area = list(ESTRUTURA_AREAS_TEMATICAS[nome_area].keys())

    # Para cada ramificação, buscar as ONGs que nela operam
    dados_sector = []
    for nome_ramificacao in ramificacoes_da_area:
        ongs = conn.execute(f'''
            SELECT DISTINCT o.id, o.nome, o.natureza, o.origem, o.provincia, o.estado,
                            o.distritos_texto, o.area_intervencao
            FROM ongs o
            JOIN ong_ramificacoes orf ON orf.ong_id = o.id
            JOIN ramificacoes r ON r.id = orf.ramificacao_id
            WHERE r.nome = ? {cond_prov}
            ORDER BY o.nome
        ''', [nome_ramificacao] + params_prov).fetchall()

        dados_sector.append({
            'ramificacao': nome_ramificacao,
            'ongs': ongs,
            'total': len(ongs),
        })

    total_geral = conn.execute(f'''
        SELECT COUNT(DISTINCT o.id) FROM ongs o
        JOIN ong_areas oa ON oa.ong_id = o.id
        JOIN areas a ON a.id = oa.area_id
        WHERE a.nome = ? {cond_prov}
    ''', [nome_area] + params_prov).fetchone()[0]

    conn.close()

    return render_template('sector.html',
                            nome_area=nome_area,
                            dados_sector=dados_sector,
                            total_geral=total_geral,
                            provincias=PROVINCIAS,
                            provincia_filtro=provincia_filtro)


@app.route('/ong/<int:ong_id>')
def detalhe(ong_id):
    conn = get_connection()
    ong = conn.execute('SELECT * FROM ongs WHERE id = ?', (ong_id,)).fetchone()
    if not ong:
        conn.close()
        flash('ONG não encontrada.', 'warning')
        return redirect(url_for('index'))

    distritos = conn.execute('''
        SELECT d.nome FROM ong_distritos od
        JOIN distritos d ON d.id = od.distrito_id
        WHERE od.ong_id = ? ORDER BY d.nome
    ''', (ong_id,)).fetchall()

    areas = conn.execute('''
        SELECT a.nome FROM ong_areas oa
        JOIN areas a ON a.id = oa.area_id
        WHERE oa.ong_id = ? ORDER BY a.nome
    ''', (ong_id,)).fetchall()

    ramificacoes = conn.execute('''
        SELECT r.nome FROM ong_ramificacoes orf
        JOIN ramificacoes r ON r.id = orf.ramificacao_id
        WHERE orf.ong_id = ? ORDER BY r.nome
    ''', (ong_id,)).fetchall()

    conn.close()
    return render_template('detalhe.html', ong=ong, distritos=distritos, areas=areas, ramificacoes=ramificacoes)


@app.route('/ong/novo', methods=['GET', 'POST'])
@login_obrigatorio
def novo():
    conn = get_connection()
    if request.method == 'POST':
        provincia = request.form.get('provincia') or None
        area_intervencao = request.form.get('area_intervencao') or None
        distritos_texto = request.form.get('distritos_texto') or None
        dados = (
            request.form.get('nome', '').strip(),
            request.form.get('natureza') or None,
            request.form.get('origem') or None,
            provincia,
            area_intervencao,
            request.form.get('programas') or None,
            request.form.get('projetos_em_curso') or None,
            request.form.get('fonte_financiamento') or None,
            distritos_texto,
            request.form.get('perfil_grupo_alvo') or None,
            request.form.get('pessoa_contacto') or None,
            request.form.get('telefone') or None,
            request.form.get('email') or None,
            request.form.get('coordenada_x') or None,
            request.form.get('coordenada_y') or None,
            request.form.get('estado') or 'Ativo',
        )
        if not dados[0]:
            flash('O nome da organização é obrigatório.', 'danger')
        else:
            aprovacao = 'Aprovado' if e_super_admin() else 'Pendente'
            criado_por = nivel_sessao()
            cur = conn.execute('''
                INSERT INTO ongs (nome, natureza, origem, provincia, area_intervencao,
                                   programas, projetos_em_curso, fonte_financiamento, distritos_texto,
                                   perfil_grupo_alvo, pessoa_contacto, telefone, email,
                                   coordenada_x, coordenada_y, estado, aprovacao, criado_por)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', dados + (aprovacao, criado_por))
            sincronizar_tags(conn, cur.lastrowid, distritos_texto, area_intervencao, provincia)
            conn.commit()
            conn.close()
            if aprovacao == 'Pendente':
                flash('ONG registada e enviada para aprovação do Super Administrador.', 'warning')
            else:
                flash('ONG registada e aprovada com sucesso.', 'success')
            return redirect(url_for('index'))
    conn.close()
    return render_template('formulario.html', ong=None, provincias=PROVINCIAS)


@app.route('/ong/<int:ong_id>/editar', methods=['GET', 'POST'])
@login_obrigatorio
def editar(ong_id):
    conn = get_connection()
    ong = conn.execute('SELECT * FROM ongs WHERE id = ?', (ong_id,)).fetchone()
    if not ong:
        conn.close()
        flash('ONG não encontrada.', 'warning')
        return redirect(url_for('index'))

    if request.method == 'POST':
        provincia = request.form.get('provincia') or None
        area_intervencao = request.form.get('area_intervencao') or None
        distritos_texto = request.form.get('distritos_texto') or None
        conn.execute('''
            UPDATE ongs SET nome=?, natureza=?, origem=?, provincia=?, area_intervencao=?,
                            programas=?, projetos_em_curso=?, fonte_financiamento=?, distritos_texto=?,
                            perfil_grupo_alvo=?, pessoa_contacto=?, telefone=?, email=?,
                            coordenada_x=?, coordenada_y=?, estado=?
            WHERE id=?
        ''', (
            request.form.get('nome', '').strip(),
            request.form.get('natureza') or None,
            request.form.get('origem') or None,
            provincia,
            area_intervencao,
            request.form.get('programas') or None,
            request.form.get('projetos_em_curso') or None,
            request.form.get('fonte_financiamento') or None,
            distritos_texto,
            request.form.get('perfil_grupo_alvo') or None,
            request.form.get('pessoa_contacto') or None,
            request.form.get('telefone') or None,
            request.form.get('email') or None,
            request.form.get('coordenada_x') or None,
            request.form.get('coordenada_y') or None,
            request.form.get('estado') or 'Ativo',
            ong_id,
        ))
        sincronizar_tags(conn, ong_id, distritos_texto, area_intervencao, provincia)
        conn.commit()
        conn.close()
        flash('ONG atualizada com sucesso.', 'success')
        return redirect(url_for('detalhe', ong_id=ong_id))

    conn.close()
    return render_template('formulario.html', ong=ong, provincias=PROVINCIAS)


@app.route('/ong/<int:ong_id>/eliminar', methods=['POST'])
@super_admin_obrigatorio
def eliminar(ong_id):
    conn = get_connection()
    conn.execute('DELETE FROM ongs WHERE id = ?', (ong_id,))
    conn.commit()
    conn.close()
    flash('ONG eliminada.', 'info')
    return redirect(url_for('index'))


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
