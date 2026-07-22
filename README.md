# SGIONGs — Filtragem de ONGs/OSCs (Moçambique — 11 províncias)

Aplicação web para listar e filtrar ONGs/OSCs a partir das matrizes de
recolha de informação ("Matriz de Recolha de Informação sobre ONG's que
Operam em Moçambique"), de qualquer província do país.

**Stack:** Python 3 + Flask + SQLite + Bootstrap 5

---

## 1. Estrutura do projeto

```
sigeong_gaza/
├── app.py                 → aplicação Flask (rotas, filtros, CRUD)
├── database.py            → ligação e inicialização da base SQLite
├── importar_excel.py      → importa os ficheiros .xlsx para a base de dados
├── tagging.py             → lista oficial das 11 províncias/distritos + deteção de áreas
├── schema.sql             → estrutura das tabelas
├── requirements.txt
├── data/
│   ├── matriz_ongs.xlsx   → coloca aqui o(s) ficheiro(s) .xlsx (um por província)
│   └── ongs.db            → base de dados SQLite (gerada automaticamente)
├── templates/             → páginas HTML (Bootstrap 5)
└── static/css/style.css
```

## 2. Pré-requisitos

- Python 3.10 ou superior instalado
- Não precisa de MySQL, Laragon nem servidor web — tudo corre localmente com SQLite

## 3. Instalação (passo a passo)

```bash
cd sigeong_gaza
python -m venv venv
venv\Scripts\activate          (Windows)  /  source venv/bin/activate (Linux/Mac)
pip install -r requirements.txt
python importar_excel.py
python app.py
```

Abrir no browser: **http://127.0.0.1:5000**

## 4. Importar dados de várias províncias

A **província é detetada automaticamente** a partir da célula
`"Província de: <nome>"` que existe no cabeçalho de cada matriz — não é
preciso indicar manualmente qual é.

Para ter o registo nacional completo, coloca um ficheiro `.xlsx` por
província dentro da pasta `data/` (ex.: `GAZA_-_Matriz...xlsx`,
`NAMPULA_-_Matriz...xlsx`, `SOFALA_-_Matriz...xlsx`, etc.) e corre:

```bash
python importar_excel.py
```

Isto importa **todos** os `.xlsx` encontrados em `data/`. Cada ficheiro só
substitui os registos da sua própria província — importar Nampula não
apaga os dados já existentes de Gaza, Sofala, etc.

Também é possível importar um único ficheiro ou uma pasta diferente:

```bash
python importar_excel.py "C:\caminho\para\NAMPULA.xlsx"
python importar_excel.py "C:\caminho\para\pasta_com_varios_ficheiros"
```

⚠️ Se o ficheiro não tiver a célula `"Província de: <nome>"` no cabeçalho,
a importação desse ficheiro é ignorada (com aviso no terminal) — é assim
que evitamos misturar dados sem saber a que província pertencem.

## 5. Funcionalidades

- **Listagem com filtros**: nome, **província**, origem (Nacional/Internacional),
  distrito, área de intervenção e estado (Ativo/Inativo/Suspenso)
- **Deteção automática** de província, distritos beneficiários e áreas de
  intervenção a partir do texto livre da matriz
- **Detalhe de cada ONG** com todos os campos
- **Registar / Editar / Eliminar** ONGs diretamente na aplicação (com
  seletor de província)
- **Paginação** (12 organizações por página)
- Cobertura das **11 províncias**: Niassa, Cabo Delgado, Nampula, Zambézia,
  Tete, Manica, Sofala, Gaza, Inhambane, Maputo Província e Maputo Cidade

## 6. Disponibilizar na rede interna do escritório

Por defeito (`python app.py`), o site só é acessível no teu próprio computador
(`http://127.0.0.1:5000`). Para os colegas conseguirem aceder a partir dos
computadores deles, **na mesma rede** (Wi-Fi ou cabo do escritório):

```bash
python executar_rede.py
```

Depois:

1. Descobre o IP deste computador — abre outro CMD e escreve:
   ```
   ipconfig
   ```
   Procura "Endereço IPv4" (ex.: `192.168.1.45`).

2. Nos outros computadores, **ligados à mesma rede**, abrir no browser:
   ```
   http://192.168.1.45:5000
   ```
   (substituir pelo IP que encontraste)

**Importante:**
- O computador que corre `executar_rede.py` tem de ficar **ligado e com a
  app aberta** enquanto os colegas estiverem a usar.
- Isto só funciona dentro da mesma rede local (não funciona fora do
  escritório, nem pela internet, sem configuração adicional).
- O IP pode mudar se o router atribuir IPs automaticamente (DHCP). Se isso
  for um problema, pede ao responsável de TI para reservar um IP fixo para
  este computador.
- **Muda a senha do administrador** em `config.py` antes de partilhar — com
  mais pessoas a aceder, a senha por defeito deixa de ser segura.
- Liberta a porta 5000 na firewall do Windows se o acesso falhar a partir de
  outros computadores: Firewall do Windows Defender → Definições Avançadas
  → Regras de Entrada → Nova Regra → Porta → TCP → 5000 → Permitir.

## 7. Limitações conhecidas / próximos passos sugeridos

- As listas de distritos em `tagging.py` baseiam-se na divisão
  administrativa oficial mais recente disponível; se um distrito novo for
  criado ou o nome mudar, basta adicionar/ajustar uma entrada no dicionário
  `DISTRITOS_POR_PROVINCIA`.
- A deteção de distritos/áreas é feita por palavras-chave em texto livre —
  revisar `tagging.py` para ajustar ou ampliar.
- Sem autenticação/login — uso pensado para um único posto de trabalho
  interno. Acesso multiutilizador com permissões (admin/técnico/visualização)
  é um passo seguinte a desenvolver, se necessário.

## 8. Resolução de problemas

- **"python não é reconhecido..."** → instalar Python e marcar "Add Python
  to PATH" durante a instalação.
- **Porta 5000 ocupada** → editar a última linha de `app.py` para
  `app.run(debug=True, port=5050)`.
- **Província não detetada ao importar** → confirmar que existe uma célula
  com o texto `"Província de: <nome>"` nas primeiras linhas da folha, e que
  o nome corresponde a uma das 11 províncias (ver `tagging.py` → `PROVINCIAS`).

## 9. Publicar na internet (Render.com)

Este projeto já inclui `wsgi.py`, `Procfile` e `render.yaml`, prontos para o
Render detetar sozinho. Passos resumidos:

1. Enviar o conteúdo **desta pasta** (`sigeong_gaza`) para um repositório no
   GitHub — o `app.py`, `wsgi.py` e `requirements.txt` têm de ficar na
   **raiz do repositório**, não dentro de outra subpasta.
2. Criar um "New Web Service" no Render, escolher o repositório e deixar o
   `render.yaml` configurar tudo automaticamente.

**Erro mais comum:** `python: can't open file '.../src/wsgi.py': No such
file or directory`. Isto acontece quando o repositório tem esta pasta
(`sigeong_gaza`) aninhada dentro de outra no GitHub. Duas formas de resolver:

- No Render, ir a **Settings → Root Directory** e escrever `sigeong_gaza`; ou
- Reorganizar o repositório para que o conteúdo desta pasta fique
  diretamente na raiz (fazer `git init`/`git add .` **de dentro** desta
  pasta, não da pasta que a contém).

No plano gratuito, o serviço "adormece" após inatividade — o primeiro
acesso pode demorar 30–60 segundos a responder; isto é normal e não é falha
de código.

