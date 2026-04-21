from init_db import ensure_usuarios_password_column
from repositories.usuarios_repo import get_user_by_codigo, update_user_password


def main():
    ensure_usuarios_password_column()

    codigo_usuario = input("Código do usuário: ").strip()
    password = input("Nova senha do usuário: ").strip()

    if not codigo_usuario or not password:
        print("Código do usuário e senha são obrigatórios.")
        return

    usuario = get_user_by_codigo(codigo_usuario)
    if not usuario:
        print("Usuário não encontrado. Nenhuma alteração foi realizada.")
        return

    updated = update_user_password(usuario["id"], password)
    if updated:
        print("Senha do usuário atualizada com sucesso.")
        return

    print("Não foi possível atualizar a senha do usuário.")


if __name__ == "__main__":
    main()
