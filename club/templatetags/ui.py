from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from club.icons import ICONS

register = template.Library()


@register.simple_tag
def icon(name, size=18, cls=''):
    """Встраивает SVG-иконку: {% icon 'users' %}."""
    return format_html('<svg class="i {}" width="{}" height="{}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
                       'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{}</svg>',
                       cls, size, size, mark_safe(ICONS.get(name, '')))


@register.filter
def initials(person):
    """Инициалы для аватара: «Иванов Иван» → «ИИ»."""
    return (person.last_name[:1] + person.first_name[:1]).upper()


@register.filter
def tone(value):
    """Номер цвета аватара по id (0–5)."""
    return (value or 0) % 6
