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
