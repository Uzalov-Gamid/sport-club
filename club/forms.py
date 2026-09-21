from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group as AuthGroup
from django.db import IntegrityError

from .models import Client, Enrollment, Group, Hall, Section, Subscription, Trainer, Visit
from .roles import OPERATOR_GROUP

User = get_user_model()
DATE = forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d')
TIME = forms.TimeInput(attrs={'type': 'time'}, format='%H:%M')


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = '__all__'
        widgets = {'birth_date': DATE}


class SectionForm(forms.ModelForm):
    class Meta:
        model = Section
        fields = '__all__'


class TrainerForm(forms.ModelForm):
    class Meta:
        model = Trainer
        fields = '__all__'


class HallForm(forms.ModelForm):
    class Meta:
        model = Hall
        fields = '__all__'


class GroupForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = '__all__'
        widgets = {'start_time': TIME}
        help_texts = {'duration_min': 'Если не указать — БД установит 60 минут (триггер).'}


class EnrollmentForm(forms.ModelForm):
    class Meta:
        model = Enrollment
        fields = '__all__'
        widgets = {'created_at': DATE}
