# config.py
# Credenciais de acesso dos utilizadores do SGIONGs.
#
# Existem dois níveis de acesso:
#
#   ADMIN (Administrador)
#     - Pode registar e editar ONGs
#     - Os registos ficam como "Pendente" até aprovação do Super Admin
#     - Não pode eliminar ONGs nem aprovar registos
#
#   SUPER ADMIN (Super Administrador)
#     - Pode fazer tudo o que o Admin faz
#     - Aprova ou rejeita os registos lançados pelo Admin
#     - Pode eliminar ONGs
#     - Vê todos os registos (incluindo pendentes e rejeitados)
#
# ALTERE as senhas abaixo antes de usar o sistema.

ADMIN_USERNAME = 'adminong'
ADMIN_PASSWORD = 'admin2026'

SUPER_ADMIN_USERNAME = 'superadmin'
SUPER_ADMIN_PASSWORD = 'superadmin2026'
