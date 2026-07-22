-- SGIONGs | Base de dados de ONGs/OSCs
-- SQLite

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS ongs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numero_original INTEGER,
    nome TEXT NOT NULL,
    natureza TEXT,                  -- ONG / OSC / Fundação
    origem TEXT,                    -- Nacional / Internacional / Nacional e Internacional
    provincia TEXT,
    area_intervencao TEXT,          -- "Área/s Temática/s" no template oficial
    programas TEXT,                 -- "Programas" (distinto de Projectos em Curso)
    projetos_em_curso TEXT,         -- "Projectos" / "Projectos em Curso"
    fonte_financiamento TEXT,
    distritos_texto TEXT,           -- "Distrito/Município" / "Distritos Beneficiários"
    perfil_grupo_alvo TEXT,
    pessoa_contacto TEXT,           -- "Ponto Focal" / "Pessoa de Contacto"
    telefone TEXT,
    email TEXT,
    coordenada_x TEXT,               -- "Coordenadas UTM" X
    coordenada_y TEXT,               -- "Coordenadas UTM" Y
    estado TEXT DEFAULT 'Ativo',    -- Ativo / Inativo / Suspenso
    aprovacao TEXT DEFAULT 'Aprovado', -- Pendente / Aprovado / Rejeitado
    motivo_rejeicao TEXT,            -- preenchido pelo Super Admin ao rejeitar
    aprovado_por TEXT,               -- utilizador que aprovou/rejeitou
    aprovado_em TIMESTAMP,           -- quando foi aprovado/rejeitado
    criado_por TEXT,                 -- 'admin' ou 'superadmin' ou 'importacao'
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS distritos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT UNIQUE NOT NULL,
    provincia TEXT
);

CREATE TABLE IF NOT EXISTS ong_distritos (
    ong_id INTEGER NOT NULL,
    distrito_id INTEGER NOT NULL,
    PRIMARY KEY (ong_id, distrito_id),
    FOREIGN KEY (ong_id) REFERENCES ongs(id) ON DELETE CASCADE,
    FOREIGN KEY (distrito_id) REFERENCES distritos(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS areas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS ong_areas (
    ong_id INTEGER NOT NULL,
    area_id INTEGER NOT NULL,
    PRIMARY KEY (ong_id, area_id),
    FOREIGN KEY (ong_id) REFERENCES ongs(id) ON DELETE CASCADE,
    FOREIGN KEY (area_id) REFERENCES areas(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ramificacoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT UNIQUE NOT NULL,
    area_id INTEGER NOT NULL,
    FOREIGN KEY (area_id) REFERENCES areas(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ong_ramificacoes (
    ong_id INTEGER NOT NULL,
    ramificacao_id INTEGER NOT NULL,
    PRIMARY KEY (ong_id, ramificacao_id),
    FOREIGN KEY (ong_id) REFERENCES ongs(id) ON DELETE CASCADE,
    FOREIGN KEY (ramificacao_id) REFERENCES ramificacoes(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_ongs_nome ON ongs(nome);
CREATE INDEX IF NOT EXISTS idx_ongs_origem ON ongs(origem);
CREATE INDEX IF NOT EXISTS idx_ongs_estado ON ongs(estado);
CREATE INDEX IF NOT EXISTS idx_ongs_provincia ON ongs(provincia);
