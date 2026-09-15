"""Бизнес-логика: запросы по заданию, расчёт стоимости, расписание залов."""
from datetime import date
from decimal import Decimal

from django.db.models import Count, Q

from .models import WEEKDAYS, Client, Enrollment, Group, Section, Subscription, Visit


def groups_with_client_counts(on_date=None):
    """Запрос 1: список групп с количеством клиентов на сегодняшний день."""
    return (Group.objects.select_related('section', 'trainer', 'hall')
            .annotate(clients=Count('enrollments', filter=Q(enrollments__status=Enrollment.Status.ACTIVE)))
            .order_by('section__name', 'weekday', 'start_time'))


def clients_by_section_and_gender():
    """Запрос 2: по видам занятий — число клиентов-мужчин и клиентов-женщин.
    Клиент учитывается один раз в секции, даже если ходит в несколько её групп."""
    rows = []
    for section in Section.objects.order_by('name'):
        active = Client.objects.filter(enrollments__status=Enrollment.Status.ACTIVE,
                                       enrollments__group__section=section).distinct()
        rows.append({
            'section': section.name,
            'men': active.filter(gender=Client.Gender.MALE).count(),
            'women': active.filter(gender=Client.Gender.FEMALE).count(),
        })
    return rows
