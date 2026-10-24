"""Роли приложения: администратор и оператор (на основе групп Django)."""
ADMIN_GROUP = 'Администратор'
OPERATOR_GROUP = 'Оператор'
CLIENT_GROUP = 'Клиент'


def is_admin(user):
    return user.is_authenticated and (user.is_superuser or user.groups.filter(name=ADMIN_GROUP).exists())


def is_operator(user):
    return user.is_authenticated and (is_admin(user) or user.groups.filter(name=OPERATOR_GROUP).exists())


def is_client(user):
    """Клиент клуба с личным кабинетом (не сотрудник)."""
    return (user.is_authenticated and not is_operator(user)
            and hasattr(user, 'client_profile') and user.groups.filter(name=CLIENT_GROUP).exists())


def role_name(user):
    if is_admin(user):
        return 'Администратор'
    if is_operator(user):
        return 'Оператор'
    return 'Клиент' if is_client(user) else 'Без роли'
