import sqlite3
import os

from tagging import ESTRUTURA_AREAS_TEMATICAS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'data', 'ongs.db')
SCHEMA_PATH = os.path.join(BASE_DIR, 'schema.sql')


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def init_db():
    os.makedirs(os.path.join(BASE_DIR, 'data'), exist_ok=True)
    conn = get_connection()
    with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
        conn.executescript(f.read())
    _semear_taxonomia_fixa(conn)
    conn.commit()
    conn.close()


def _semear_taxonomia_fixa(conn):
    """Garante que as 8 áreas temáticas e as suas ramificações oficiais
    existem sempre na base de dados, mesmo antes de qualquer importação —
    para que apareçam nos filtros com 0 em vez de não aparecerem."""
    for area, ramificacoes in ESTRUTURA_AREAS_TEMATICAS.items():
        conn.execute('INSERT OR IGNORE INTO areas (nome) VALUES (?)', (area,))
        area_id = conn.execute('SELECT id FROM areas WHERE nome = ?', (area,)).fetchone()['id']
        for sub in ramificacoes:
            conn.execute('INSERT OR IGNORE INTO ramificacoes (nome, area_id) VALUES (?, ?)', (sub, area_id))
