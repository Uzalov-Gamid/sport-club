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
