from datetime import date

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from . import forms, roles, services
from .models import Client, Enrollment, Group, Hall, Section, Subscription, Trainer, Visit


class OperatorRequired(LoginRequiredMixin, UserPassesTestMixin):
    """Доступ для оператора и администратора."""
    def test_func(self):
        return roles.is_operator(self.request.user)


class AdminRequired(LoginRequiredMixin, UserPassesTestMixin):
    """Доступ только для администратора."""
    def test_func(self):
        return roles.is_admin(self.request.user)


class HomeView(OperatorRequired, View):
    def get(self, request):
        return render(request, 'club/home.html', {'role': roles.role_name(request.user),
                                                  'is_admin': roles.is_admin(request.user)})


# ---- Универсальные CRUD-формы для таблиц ----
class CrudConfig:
    def __init__(self, key, title, model, form, columns, access):
        self.key, self.title, self.model, self.form, self.columns, self.access = \
            key, title, model, form, columns, access


CONFIGS = [
    CrudConfig('clients', 'Клиенты', Client, forms.ClientForm,
               ['last_name', 'first_name', 'patronymic', 'gender', 'birth_date', 'phone'], OperatorRequired),
    CrudConfig('enrollments', 'Записи на занятия', Enrollment, forms.EnrollmentForm,
               ['client', 'group', 'status', 'created_at'], OperatorRequired),
    CrudConfig('visits', 'Посещения', Visit, forms.VisitForm, ['enrollment', 'date', 'attended'], OperatorRequired),
    CrudConfig('subscriptions', 'Абонементы', Subscription, forms.SubscriptionForm,
               ['client', 'discount_percent', 'start_date', 'end_date'], OperatorRequired),
    CrudConfig('groups', 'Группы занятий', Group, forms.GroupForm,
               ['section', 'trainer', 'hall', 'weekday', 'start_time', 'duration_min', 'price'], AdminRequired),
    CrudConfig('sections', 'Секции', Section, forms.SectionForm, ['name'], AdminRequired),
    CrudConfig('trainers', 'Тренеры', Trainer, forms.TrainerForm,
               ['last_name', 'first_name', 'patronymic', 'phone'], AdminRequired),
    CrudConfig('halls', 'Залы', Hall, forms.HallForm, ['number', 'name'], AdminRequired),
]


def _cell(obj, field):
    f = obj._meta.get_field(field)
    value = getattr(obj, f'get_{field}_display')() if f.choices else getattr(obj, field)
    if value is True: return 'да'
    if value is False: return 'нет'
    return '—' if value in (None, '') else value


def build_views(cfg):
    ctx = {'cfg': cfg}

    class List(cfg.access, ListView):
        model = cfg.model
        template_name = 'club/crud_list.html'
        paginate_by = 20

        def get_context_data(self, **kw):
            c = super().get_context_data(**kw)
            c.update(ctx)
            c['headers'] = [cfg.model._meta.get_field(f).verbose_name for f in cfg.columns]
            c['rows'] = [(o, [_cell(o, f) for f in cfg.columns]) for o in c['object_list']]
            return c

    class SaveMixin:
        template_name = 'club/crud_form.html'
        form_class = cfg.form
        model = cfg.model
        success_url = reverse_lazy(f'club:{cfg.key}')

        def get_context_data(self, **kw):
            c = super().get_context_data(**kw); c.update(ctx); return c

        def form_valid(self, form):
            try:
                response = super().form_valid(form)
            except IntegrityError as e:
                form.add_error(None, f'Ограничение базы данных: {e}')
                return self.form_invalid(form)
            messages.success(self.request, 'Сохранено.')
            return response

    class Create(cfg.access, SaveMixin, CreateView): pass
    class Edit(cfg.access, SaveMixin, UpdateView): pass

    class Delete(cfg.access, DeleteView):
        model = cfg.model
        template_name = 'club/crud_delete.html'
        success_url = reverse_lazy(f'club:{cfg.key}')

        def get_context_data(self, **kw):
            c = super().get_context_data(**kw); c.update(ctx); return c

        def form_valid(self, form):
            from django.db.models import ProtectedError
            try:
                return super().form_valid(form)
            except ProtectedError:
                messages.error(self.request, 'Нельзя удалить: на запись ссылаются другие данные.')
                return redirect(self.success_url)

    return List.as_view(), Create.as_view(), Edit.as_view(), Delete.as_view()
