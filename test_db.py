from repositories.usuarios_repo import get_user_by_codigo
from repositories.links_repo import get_all_links

usuario = get_user_by_codigo("CAIO001")
print("Usuário:", dict(usuario) if usuario else None)

links = get_all_links()
print("Links:", [dict(l) for l in links])