from . import roles


def role(request):
    """Роль текущего пользователя доступна во всех шаблонах (меню, заголовок)."""
    user = request.user
    return {'role_name': roles.role_name(user), 'is_admin': roles.is_admin(user)}
