from datetime import date, datetime, timedelta
from functools import wraps

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import DatabaseError, IntegrityError, transaction
from django.db.models import ProtectedError, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from . import forms, roles, services
from .models import WEEKDAYS, Client, Enrollment, Group, Hall, Section, Subscription, Trainer, Visit


def access(check):
    """Доступ только после входа и только при выполнении проверки роли (иначе 403)."""
    def decorator(view):
        @wraps(view)
        def inner(request, *args, **kwargs):
            if not check(request.user):
                raise PermissionDenied
            return view(request, *args, **kwargs)
        return login_required(inner)
    return decorator


operator_required = access(roles.is_operator)
client_required = access(roles.is_client)
admin_required = access(roles.is_admin)


def _next(request, default, *args):
    """Куда вернуться после действия: переданный адрес этого же сайта или страница по умолчанию."""
    target = request.POST.get('next')
    if target and url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}):
        return redirect(target)
    return redirect(default, *args)


def _form_errors(request, form):
    for field, errs in form.errors.items():
        label = form.fields[field].label if field in form.fields else ''
        for e in errs:
            messages.error(request, f'{label}: {e}' if label else str(e))


def _save(request, form, ok_text):
    """Сохраняет форму; ошибки проверки и ограничений БД показываются сообщением. Возвращает объект или None."""
    if not form.is_valid():
        _form_errors(request, form)
        return None
    try:
        with transaction.atomic():
            obj = form.save()
    except IntegrityError as e:
        messages.error(request, f'Не удалось сохранить: {e}')
        return None
    messages.success(request, ok_text)
    return obj


def _enroll(request, client, group, status):
    """Запись клиента в группу с проверкой лимита; триггер БД срабатывает, даже если проверка формы обойдена."""
    if status not in Enrollment.Status.values:
        status = Enrollment.Status.ACTIVE
    if Enrollment.objects.filter(client=client, group=group).exists():
        messages.error(request, 'Клиент уже записан в эту группу.')
        return None
    enrollment = Enrollment(client=client, group=group, status=status)
    try:
        enrollment.full_clean(exclude=['created_at'])
        with transaction.atomic():
            enrollment.save()
    except ValidationError as e:
        messages.error(request, ' '.join(e.messages))
        return None
    except (IntegrityError, DatabaseError) as e:
        messages.error(request, 'В группе уже 10 человек.' if '10' in str(e) else f'Не удалось записать: {e}')
        return None
    messages.success(request, f'{client} записан(а) в группу «{group.section}».')
    return enrollment


# ---------- Главная ----------
@login_required
def home(request):
    if roles.is_client(request.user):
        return redirect('club:me')
    if not roles.is_operator(request.user):
        raise PermissionDenied
    today = date.today()
    groups = list(services.groups_with_client_counts())
    todays = sorted((g for g in groups if g.weekday == today.weekday()), key=lambda g: g.start_time)
    month_start = today.replace(day=1)
    visits_30 = Visit.objects.filter(date__gte=today - timedelta(days=30))
    total_30 = visits_30.count()
    stats = [
        ('users', 'Клиентов', Client.objects.count(), f'+{Client.objects.filter(joined__gte=month_start).count()} за месяц'),
        ('activity', 'Занимаются', Enrollment.objects.filter(status=Enrollment.Status.ACTIVE).values('client').distinct().count(),
         f'{Enrollment.objects.filter(status=Enrollment.Status.BOOKED).count()} ждут подтверждения'),
        ('calendar-check', 'Посещаемость', f'{round(visits_30.filter(attended=True).count() * 100 / total_30) if total_30 else 0}%',
         'за 30 дней'),
        ('ticket', 'Абонементы', Subscription.objects.filter(start_date__lte=today, end_date__gte=today).count(), 'действуют сейчас'),
    ]
    fill = [{'name': str(g.section), 'hall': str(g.hall), 'when': f'{g.weekday_short} {g.start_time:%H:%M}',
             'n': g.clients, 'pct': g.clients * 10, 'color': g.section_id % 6} for g in groups]
    by_gender = services.clients_by_section_and_gender()
    for row in by_gender:
        total = row['men'] + row['women']
        row['men_pct'] = round(row['men'] * 100 / total) if total else 0
        row['women_pct'] = 100 - row['men_pct'] if total else 0
    return render(request, 'club/home.html', {
        'stats': stats, 'fill': fill, 'by_gender': by_gender, 'todays': todays, 'today': today,
        'weekday': WEEKDAYS[today.weekday()], 'chart': services.attendance_by_day(),
        'expiring': services.expiring_subscriptions(), 'recent': Client.objects.order_by('-joined', '-pk')[:5]})


# ---------- Клиенты ----------
@operator_required
def clients(request):
    q = request.GET.get('q', '').strip()
    show = request.GET.get('show', 'all')
    today = date.today()
    qs = Client.objects.all()
    if q:
        qs = qs.filter(Q(last_name__icontains=q) | Q(first_name__icontains=q) | Q(patronymic__icontains=q)
                       | Q(phone__icontains=q) | Q(email__icontains=q))
    active = Q(enrollments__status=Enrollment.Status.ACTIVE)
    if show == 'active':
        qs = qs.filter(active).distinct()
    elif show == 'idle':
        qs = qs.exclude(active)
    elif show == 'sub':
        qs = qs.filter(subscriptions__start_date__lte=today, subscriptions__end_date__gte=today).distinct()
    if request.GET.get('export') == 'csv':
        return _clients_csv(qs)
    page = Paginator(qs, 15).get_page(request.GET.get('page'))
    for c in page:
        c.sections = sorted({e.group.section.name for e in c.enrollments.filter(status=Enrollment.Status.ACTIVE)
                             .select_related('group__section')})
        c.discount = services.discount_on(c, today)
        last = Visit.objects.filter(enrollment__client=c, attended=True).order_by('-date').first()
        c.last_visit = last.date if last else None
    filters = [('all', 'Все'), ('active', 'Занимаются'), ('idle', 'Без занятий'), ('sub', 'С абонементом')]
    return render(request, 'club/clients.html', {'page': page, 'q': q, 'show': show, 'filters': filters,
                                                 'total': qs.count(), 'form': forms.ClientForm()})


def _clients_csv(qs):
    import csv
    from django.http import HttpResponse
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="clients.csv"'
    response.write('\ufeff')
    w = csv.writer(response, delimiter=';')
    w.writerow(['Фамилия', 'Имя', 'Отчество', 'Пол', 'Дата рождения', 'Телефон', 'E-mail', 'Клиент с'])
    for c in qs:
        w.writerow([c.last_name, c.first_name, c.patronymic, c.get_gender_display(), f'{c.birth_date:%d.%m.%Y}',
                    c.phone, c.email, f'{c.joined:%d.%m.%Y}'])
    return response


@operator_required
@require_POST
def client_add(request):
    client = _save(request, forms.ClientForm(request.POST), 'Клиент добавлен.')
    return redirect('club:client', client.pk) if client else redirect('club:clients')


@operator_required
def client_detail(request, pk):
    client = get_object_or_404(Client, pk=pk)
    today = date.today()
    enrollments = list(client.enrollments.select_related('group__section', 'group__trainer', 'group__hall'))
    todays = {v.enrollment_id: v for v in Visit.objects.filter(enrollment__client=client, date=today)}
    for e in enrollments:
        e.today_visit = todays.get(e.pk)
    enrolled_ids = [e.group_id for e in enrollments]
    free_groups = [g for g in services.groups_with_client_counts() if g.pk not in enrolled_ids]
    for g in free_groups:
        g.free = 10 - g.clients
    cost_form = forms.CostForm(request.GET or None)
    d1 = d2 = None
    if cost_form.is_valid():
        d1, d2 = cost_form.cleaned_data['date_from'], cost_form.cleaned_data['date_to']
    cost_rows, total = services.client_cost(client, d1, d2)
    history = (Visit.objects.filter(enrollment__client=client).select_related('enrollment__group__section')
               .order_by('-date')[:12])
    return render(request, 'club/client.html', {
        'c': client, 'stats': services.client_stats(client, today), 'history': history, 'enrollments': enrollments, 'free_groups': free_groups, 'today': today,
        'subscriptions': client.subscriptions.all(), 'discount': services.discount_on(client, today),
        'sub_form': forms.SubscriptionForm(initial={'discount_percent': 5, 'start_date': today}),
        'form': forms.ClientForm(instance=client), 'cost_form': cost_form, 'cost_rows': cost_rows,
        'total': total, 'statuses': Enrollment.Status.choices,
        'show_cost': 'date_from' in request.GET or 'date_to' in request.GET})


@operator_required
@require_POST
def client_edit(request, pk):
    client = get_object_or_404(Client, pk=pk)
    _save(request, forms.ClientForm(request.POST, instance=client), 'Данные клиента сохранены.')
    return redirect('club:client', pk)


@operator_required
@require_POST
def client_delete(request, pk):
    client = get_object_or_404(Client, pk=pk)
    client.delete()
    messages.success(request, f'Клиент «{client}» удалён.')
    return redirect('club:clients')


@operator_required
@require_POST
def client_enroll(request, pk):
    client = get_object_or_404(Client, pk=pk)
    group = get_object_or_404(Group, pk=request.POST.get('group') or 0)
    _enroll(request, client, group, request.POST.get('status'))
    return redirect('club:client', pk)


@operator_required
@require_POST
def subscription_add(request, pk):
    client = get_object_or_404(Client, pk=pk)
    form = forms.SubscriptionForm(request.POST, instance=Subscription(client=client))
    _save(request, form, 'Абонемент оформлен.')
    return redirect('club:client', pk)


@operator_required
@require_POST
def subscription_delete(request, pk):
    sub = get_object_or_404(Subscription, pk=pk)
    sub.delete()
    messages.success(request, 'Абонемент удалён.')
    return redirect('club:client', sub.client_id)


# ---------- Записи и посещения ----------
@operator_required
@require_POST
def enrollment_status(request, pk):
    e = get_object_or_404(Enrollment, pk=pk)
    status = request.POST.get('status')
    if status not in Enrollment.Status.values:
        raise Http404
    e.status = status
    try:
        e.full_clean(exclude=['created_at'])
        with transaction.atomic():
            e.save()
        messages.success(request, 'Статус записи изменён.')
    except ValidationError as err:
        messages.error(request, ' '.join(err.messages))
    except (IntegrityError, DatabaseError):
        messages.error(request, 'В группе уже 10 человек.')
    return _next(request, 'club:client', e.client_id)


@operator_required
@require_POST
def enrollment_delete(request, pk):
    e = get_object_or_404(Enrollment, pk=pk)
    e.delete()
    messages.success(request, 'Запись удалена.')
    return _next(request, 'club:client', e.client_id)


@operator_required
@require_POST
def visit_mark(request, pk):
    """Быстрая отметка посещения на дату: был (1) или пропуск (0)."""
    e = get_object_or_404(Enrollment, pk=pk)
    try:
        day = datetime.strptime(request.POST.get('date', ''), '%Y-%m-%d').date()
    except ValueError:
        day = date.today()
    attended = request.POST.get('attended') == '1'
    Visit.objects.update_or_create(enrollment=e, date=day, defaults={'attended': attended, 'self_marked': False})
    messages.success(request, f'{e.client}: {"был(а)" if attended else "пропуск"}, {day:%d.%m.%Y}.')
    return _next(request, 'club:client', e.client_id)


@operator_required
@require_POST
def visit_clear(request, pk):
    e = get_object_or_404(Enrollment, pk=pk)
    Visit.objects.filter(enrollment=e, date=request.POST.get('date')).delete()
    return _next(request, 'club:client', e.client_id)


# ---------- Группы и расписание ----------
@operator_required
def timetable(request):
    sections = [(s, s.pk % 6) for s in Section.objects.all()]
    return render(request, 'club/timetable.html', {'days': services.week_timetable(), 'form': forms.GroupForm(),
                                                   'sections': sections})


@operator_required
def group_detail(request, pk):
    group = get_object_or_404(services.groups_with_client_counts(), pk=pk)
    try:
        day = datetime.strptime(request.GET.get('date', ''), '%Y-%m-%d').date()
    except ValueError:
        day = date.today()
    enrollments = list(group.enrollments.exclude(status=Enrollment.Status.CANCELLED).select_related('client'))
    visits = {v.enrollment_id: v for v in Visit.objects.filter(enrollment__group=group, date=day)}
    for e in enrollments:
        e.visit = visits.get(e.pk)
    taken = {e.client_id for e in group.enrollments.all()}
    free_clients = Client.objects.exclude(pk__in=taken)
    return render(request, 'club/group.html', {
        'g': group, 'enrollments': enrollments, 'day': day, 'free_clients': free_clients,
        'prev': day - timedelta(days=7), 'next': day + timedelta(days=7), 'is_class_day': day.weekday() == group.weekday,
        'present': sum(1 for e in enrollments if e.visit and e.visit.attended),
        'form': forms.GroupForm(instance=group), 'places': 10 - group.clients,
        'statuses': Enrollment.Status.choices})


@admin_required
@require_POST
def group_add(request):
    group = _save(request, forms.GroupForm(request.POST), 'Группа создана.')
    return redirect('club:group', group.pk) if group else redirect('club:timetable')


@admin_required
@require_POST
def group_edit(request, pk):
    group = get_object_or_404(Group, pk=pk)
    _save(request, forms.GroupForm(request.POST, instance=group), 'Группа сохранена.')
    return redirect('club:group', pk)


@admin_required
@require_POST
def group_delete(request, pk):
    group = get_object_or_404(Group, pk=pk)
    group.delete()
    messages.success(request, 'Группа удалена.')
    return redirect('club:timetable')


@operator_required
@require_POST
def group_enroll(request, pk):
    group = get_object_or_404(Group, pk=pk)
    client = get_object_or_404(Client, pk=request.POST.get('client') or 0)
    _enroll(request, client, group, request.POST.get('status'))
    return redirect('club:group', pk)


@operator_required
@require_POST
def group_attendance(request, pk):
    """Отметка всей группы на дату: отмеченные — присутствовали, остальные активные — пропуск."""
    group = get_object_or_404(Group, pk=pk)
    try:
        day = datetime.strptime(request.POST.get('date', ''), '%Y-%m-%d').date()
    except ValueError:
        day = date.today()
    present = set(request.POST.getlist('present'))
    saved = 0
    for e in group.enrollments.filter(status=Enrollment.Status.ACTIVE):
        Visit.objects.update_or_create(enrollment=e, date=day, defaults={'attended': str(e.pk) in present, 'self_marked': False})
        saved += 1
    messages.success(request, f'Посещаемость за {day:%d.%m.%Y} сохранена ({saved} чел.).')
    return redirect(f"{reverse('club:group', args=[pk])}?date={day:%Y-%m-%d}")


# ---------- Отчёты ----------
@operator_required
def reports(request):
    tab = request.GET.get('tab', 'groups')
    ctx = {'tab': tab if tab in ('groups', 'gender', 'hall') else 'groups', 'today': date.today()}
    if ctx['tab'] == 'groups':
        ctx['groups'] = services.groups_with_client_counts()
    elif ctx['tab'] == 'gender':
        ctx['rows'] = services.clients_by_section_and_gender()
    else:
        halls = list(Hall.objects.all())
        hall = next((h for h in halls if str(h.pk) == request.GET.get('hall')), halls[0] if halls else None)
        ctx.update(halls=halls, hall=hall, schedule=services.hall_schedule(hall) if hall else [])
    return render(request, 'club/reports.html', ctx)


# ---------- Справочники и пользователи (администратор) ----------
CATALOG = {
    'sections': ('Секции', Section, forms.SectionForm),
    'trainers': ('Тренеры', Trainer, forms.TrainerForm),
    'halls': ('Залы', Hall, forms.HallForm),
}


@admin_required
def catalog(request):
    tab = request.GET.get('tab', 'sections')
    User = get_user_model()
    ctx = {'tab': tab if tab in CATALOG or tab == 'users' else 'sections', 'tabs': [(k, v[0]) for k, v in CATALOG.items()]}
    if ctx['tab'] == 'users':
        ctx.update(users=User.objects.order_by('username'), form=forms.OperatorCreateForm())
    else:
        title, model, form_cls = CATALOG[ctx['tab']]
        ctx.update(title=title, items=[(o, form_cls(instance=o)) for o in model.objects.all()], form=form_cls())
    return render(request, 'club/catalog.html', ctx)


def _catalog_entry(kind):
    if kind not in CATALOG:
        raise Http404
    return CATALOG[kind]


@admin_required
@require_POST
def catalog_add(request, kind):
    _, _, form_cls = _catalog_entry(kind)
    _save(request, form_cls(request.POST), 'Добавлено.')
    return redirect(f"{reverse('club:catalog')}?tab={kind}")


@admin_required
@require_POST
def catalog_edit(request, kind, pk):
    _, model, form_cls = _catalog_entry(kind)
    _save(request, form_cls(request.POST, instance=get_object_or_404(model, pk=pk)), 'Сохранено.')
    return redirect(f"{reverse('club:catalog')}?tab={kind}")


@admin_required
@require_POST
def catalog_delete(request, kind, pk):
    _, model, _ = _catalog_entry(kind)
    try:
        get_object_or_404(model, pk=pk).delete()
        messages.success(request, 'Удалено.')
    except ProtectedError:
        messages.error(request, 'Нельзя удалить: на запись ссылаются группы.')
    return redirect(f"{reverse('club:catalog')}?tab={kind}")


@admin_required
@require_POST
def user_add(request):
    form = forms.OperatorCreateForm(request.POST)
    if form.is_valid():
        form.save()
        messages.success(request, 'Оператор добавлен.')
    else:
        _form_errors(request, form)
    return redirect(f"{reverse('club:catalog')}?tab=users")


# ---------- Доступ клиента и личный кабинет ----------
@operator_required
@require_POST
def client_access_add(request, pk):
    client = get_object_or_404(Client, pk=pk)
    if client.user_id:
        messages.error(request, 'У клиента уже есть доступ.')
    else:
        form = forms.ClientAccessForm(request.POST)
        if form.is_valid():
            form.save(client)
            messages.success(request, f'Доступ создан, логин: {form.cleaned_data["username"]}.')
        else:
            _form_errors(request, form)
    return redirect('club:client', pk)


@operator_required
@require_POST
def client_access_delete(request, pk):
    client = get_object_or_404(Client, pk=pk)
    if client.user_id:
        client.user.delete()
        messages.success(request, 'Доступ отключён.')
    return redirect('club:client', pk)


@client_required
def me(request):
    client = request.user.client_profile
    today = timezone.localdate()
    enrollments = list(client.enrollments.exclude(status=Enrollment.Status.CANCELLED)
                       .select_related('group__section', 'group__trainer', 'group__hall'))
    todays = {v.enrollment_id: v for v in Visit.objects.filter(enrollment__client=client, date=today)}
    for e in enrollments:
        e.today_visit = todays.get(e.pk)
        e.can_checkin = (e.status == Enrollment.Status.ACTIVE and services.checkin_open(e.group)
                         and not (e.today_visit and not e.today_visit.self_marked))
    history = (Visit.objects.filter(enrollment__client=client).select_related('enrollment__group__section')
               .order_by('-date')[:15])
    stats = services.client_stats(client, today)
    now_class = next((e for e in enrollments if e.status == Enrollment.Status.ACTIVE and services.checkin_open(e.group)), None)
    return render(request, 'club/me.html', {
        'c': client, 'enrollments': enrollments, 'history': history, 'today': today, 'now_class': now_class,
        'discount': services.discount_on(client, today), 'visits_30': stats['visits_30'], 'month_total': stats['month_total']})


@client_required
@require_POST
def me_checkin(request, pk):
    """Клиент отмечает, что он на занятии: только своя активная запись и только в окне занятия."""
    e = get_object_or_404(Enrollment, pk=pk, client=request.user.client_profile)
    today = timezone.localdate()
    visit = Visit.objects.filter(enrollment=e, date=today).first()
    if e.status != Enrollment.Status.ACTIVE:
        messages.error(request, 'Запись не подтверждена, отметиться нельзя.')
    elif not services.checkin_open(e.group):
        messages.error(request, 'Отметиться можно только во время занятия (за 15 минут до начала).')
    elif visit and not visit.self_marked:
        messages.error(request, 'Посещение уже отметил оператор.')
    else:
        Visit.objects.update_or_create(enrollment=e, date=today, defaults={'attended': True, 'self_marked': True})
        messages.success(request, 'Отметка принята. Хорошей тренировки!')
    return redirect('club:me')
