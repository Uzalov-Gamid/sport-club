"""Бизнес-логика: запросы по заданию, расчёт стоимости, расписание залов."""
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.db.models import Count, Q
from django.utils import timezone

from .models import WEEKDAYS, WEEKDAYS_SHORT, Client, Enrollment, Group, Section, Subscription, Visit


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


def discount_on(client, on_date):
    """Размер скидки (%) по действующему на дату абонементу, иначе 0."""
    sub = Subscription.objects.filter(client=client, start_date__lte=on_date, end_date__gte=on_date) \
        .order_by('-discount_percent').first()
    return sub.discount_percent if sub else 0


def visit_cost(visit):
    """Стоимость одного посещённого занятия с учётом скидки абонемента."""
    if not visit.attended:
        return Decimal('0.00')
    price = Decimal(str(visit.enrollment.group.price))
    percent = discount_on(visit.enrollment.client, visit.date)
    return (price * (100 - percent) / 100).quantize(Decimal('0.01'))


def client_cost(client, date_from=None, date_to=None):
    """Стоимость занятий клиента за период: (список посещений со стоимостью, итог)."""
    qs = Visit.objects.filter(enrollment__client=client).select_related('enrollment__group__section')
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)
    rows = [(v, visit_cost(v)) for v in qs.order_by('date')]
    return rows, sum((c for _, c in rows), Decimal('0.00'))


def hall_schedule(hall):
    """Данные выходного документа: расписание зала по дням недели."""
    result = []
    groups = hall.groups.select_related('section', 'trainer').order_by('weekday', 'start_time')
    for day in range(7):
        items = [(g.start_time, g.end_time, g) for g in groups if g.weekday == day]
        if items:
            result.append((WEEKDAYS[day], items))
    return result


def week_timetable(today=None):
    """Сетка расписания на текущую неделю: 7 колонок (дни), в каждой группы по времени с заполненностью."""
    today = today or date.today()
    monday = today - timedelta(days=today.weekday())
    groups = list(groups_with_client_counts().order_by('weekday', 'start_time'))
    for g in groups:
        g.color = g.section_id % 6          # цвет карточки зависит от секции
        g.pct = g.clients * 10
    days = []
    for day in range(7):
        items = [g for g in groups if g.weekday == day]
        days.append({'name': WEEKDAYS[day], 'short': WEEKDAYS_SHORT[day], 'groups': items,
                     'date': monday + timedelta(days=day), 'today': day == today.weekday()})
    return days


CHECKIN_BEFORE = timedelta(minutes=15)


def local_now():
    return timezone.localtime()


def checkin_open(group, now=None):
    """Можно ли клиенту отметиться на занятии: в день занятия, за 15 минут до начала и до его конца."""
    now = now or local_now()
    if now.weekday() != group.weekday:
        return False
    start = datetime.combine(now.date(), group.start_time, tzinfo=now.tzinfo)
    end = datetime.combine(now.date(), group.end_time, tzinfo=now.tzinfo)
    return start - CHECKIN_BEFORE <= now <= end


def client_stats(client, today=None):
    """Показатели для карточки клиента: последнее посещение, посещения за 30 дней, посещаемость, сумма за месяц."""
    today = today or date.today()
    visits = Visit.objects.filter(enrollment__client=client)
    last = visits.filter(attended=True).order_by('-date').first()
    recent = visits.filter(date__gte=today - timedelta(days=90))
    total = recent.count()
    rate = round(recent.filter(attended=True).count() * 100 / total) if total else None
    _, month_total = client_cost(client, today.replace(day=1), today)
    return {'last_visit': last.date if last else None,
            'visits_30': visits.filter(attended=True, date__gte=today - timedelta(days=30)).count(),
            'rate': rate, 'month_total': month_total}


def attendance_by_day(days=14, today=None):
    """Сколько клиентов пришло по дням за последние N дней (для диаграммы на главной)."""
    today = today or date.today()
    start = today - timedelta(days=days - 1)
    counts = dict(Visit.objects.filter(attended=True, date__gte=start, date__lte=today)
                  .values_list('date').annotate(n=Count('id')))
    rows = [(start + timedelta(days=i), counts.get(start + timedelta(days=i), 0)) for i in range(days)]
    top = max([n for _, n in rows] + [1])
    return [{'date': d, 'n': n, 'pct': round(n * 100 / top)} for d, n in rows]


def expiring_subscriptions(days=14, today=None):
    """Абонементы, которые закончатся в ближайшие N дней."""
    today = today or date.today()
    return (Subscription.objects.filter(end_date__gte=today, end_date__lte=today + timedelta(days=days))
            .select_related('client').order_by('end_date'))
