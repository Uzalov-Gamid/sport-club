"""Роли приложения: администратор и оператор (на основе групп Django)."""
ADMIN_GROUP = 'Администратор'
OPERATOR_GROUP = 'Оператор'


def is_admin(user):
    return user.is_authenticated and (user.is_superuser or user.groups.filter(name=ADMIN_GROUP).exists())


def is_operator(user):
    return user.is_authenticated and (is_admin(user) or user.groups.filter(name=OPERATOR_GROUP).exists())


def role_name(user):
    if is_admin(user):
        return 'Администратор'
    return 'Оператор' if is_operator(user) else 'Без роли'
