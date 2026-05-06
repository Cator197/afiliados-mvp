from __future__ import annotations

STATUS_LABELS = {
    "user": {
        "na_fila": "Na fila",
        "processando": "Gerando seu link",
        "concluido": "Link gerado",
        "erro": "Não foi possível gerar o link",
        "aguardando_verificacao": "Aguardando confirmação da compra",
        "compra_confirmada": "Compra confirmada",
        "compra_nao_confirmada": "Compra não confirmada",
        "cashback_pago": "Cashback pago",
    },
    "admin": {
        "aguardando_verificacao": "Aguardando verificação",
        "compra_confirmada": "Compra confirmada",
        "compra_nao_confirmada": "Compra não confirmada",
        "cashback_pago": "Cashback pago",
        "erro": "Erro",
        "na_fila": "Na fila",
        "processando": "Processando",
        "concluido": "Concluído",
        "ativo": "Ativo",
        "inativo": "Inativo",
    },
    "worker": {
        "driver_ausente": "Navegador do robô não encontrado",
        "selenium_nao_responsivo": "Navegador não está respondendo",
        "login_necessario": "Login manual necessário",
        "ok": "Robô funcionando",
        "erro": "Robô com erro",
        "online": "Robô funcionando",
        "aguardando_login_manual": "Login manual necessário",
        "erro_recuperacao": "Robô com erro",
    },
}

STATUS_DESCRIPTIONS = {
    "user": {
        "aguardando_verificacao": "Estamos aguardando a confirmação da compra para validar seu cashback.",
        "compra_confirmada": "Sua compra foi confirmada. O cashback está em preparação.",
        "compra_nao_confirmada": "Não foi possível confirmar a compra para este link.",
        "cashback_pago": "O cashback deste link já foi pago.",
    }
}

STATUS_NEXT_ACTIONS = {
    "admin": {
        "aguardando_verificacao": "Conferir se houve compra",
        "compra_confirmada": "Preparar pagamento do cashback",
        "compra_nao_confirmada": "Nenhuma ação pendente",
        "cashback_pago": "Concluído",
        "erro": "Verificar erro ou gerar novamente",
        "na_fila": "Aguardar worker",
        "processando": "Aguardar conclusão",
        "concluido": "Aguardar criação do link",
    },
    "worker": {
        "driver_ausente": "Abra/reinicie o worker na máquina do robô.",
        "selenium_nao_responsivo": "Feche o Chrome do robô e reinicie o worker.",
        "login_necessario": "Abra o navegador do robô e faça login no Mercado Livre.",
        "ok": "Nenhuma ação necessária.",
        "erro": "Verifique o log do diagnóstico.",
        "online": "Nenhuma ação necessária.",
        "aguardando_login_manual": "Abra o navegador do robô e faça login no Mercado Livre.",
        "erro_recuperacao": "Verifique o log do diagnóstico.",
    },
}

STATUS_BADGE_CLASS = {
    "na_fila": "status-info",
    "processando": "status-processing",
    "concluido": "status-success",
    "erro": "status-danger",
    "aguardando_verificacao": "status-warning",
    "compra_confirmada": "status-info",
    "compra_nao_confirmada": "status-danger",
    "cashback_pago": "status-paid",
    "ativo": "status-success",
    "inativo": "status-muted",
}


def get_status_label(status: str | None, context: str = "user") -> str:
    if not status:
        return "Status não identificado"
    return STATUS_LABELS.get(context, {}).get(status, "Status não identificado")


def get_status_description(status: str | None, context: str = "user") -> str:
    if not status:
        return "Entre em contato com o suporte se precisar de ajuda."
    return STATUS_DESCRIPTIONS.get(context, {}).get(status, "Entre em contato com o suporte se precisar de ajuda.")


def get_status_badge_class(status: str | None) -> str:
    if not status:
        return "status-muted"
    return STATUS_BADGE_CLASS.get(status, "status-muted")


def get_status_next_action(status: str | None, context: str = "admin") -> str:
    if not status:
        return ""
    return STATUS_NEXT_ACTIONS.get(context, {}).get(status, "")
