from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group as AuthGroup
from django.db import IntegrityError

from .models import Client, Enrollment, Group, Hall, Section, Subscription, Trainer, Visit
from .roles import CLIENT_GROUP, OPERATOR_GROUP

User = get_user_model()
DATE = forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d')
TIME = forms.TimeInput(attrs={'type': 'time'}, format='%H:%M')


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ('last_name', 'first_name', 'patronymic', 'gender', 'birth_date', 'phone', 'email', 'note')
        widgets = {'birth_date': DATE, 'note': forms.Textarea(attrs={'rows': 3}),
                   'phone': forms.TextInput(attrs={'placeholder': '+7 900 000-00-00', 'inputmode': 'tel'})}


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
        help_texts = {'duration_min': 'Если оставить пустым, будет 60 минут'}


class EnrollmentForm(forms.ModelForm):
    class Meta:
        model = Enrollment
        fields = '__all__'
        widgets = {'created_at': DATE}


class SubscriptionForm(forms.ModelForm):
    class Meta:
        model = Subscription
        fields = ('discount_percent', 'start_date', 'end_date')
        widgets = {'start_date': DATE, 'end_date': DATE}


class VisitForm(forms.ModelForm):
    class Meta:
        model = Visit
        fields = '__all__'
        widgets = {'date': DATE}


class OperatorCreateForm(UserCreationForm):
    """Администратор добавляет новых пользователей с ролью «оператор»."""
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'first_name', 'last_name')

    def save(self, commit=True):
        user = super().save(commit)
        if commit:
            user.groups.add(AuthGroup.objects.get_or_create(name=OPERATOR_GROUP)[0])
        return user


class ReportForm(forms.Form):
    hall = forms.ModelChoiceField(queryset=Hall.objects.all(), label='Зал')


class CostForm(forms.Form):
    date_from = forms.DateField(required=False, widget=DATE, label='С')
    date_to = forms.DateField(required=False, widget=DATE, label='По')


class ClientAccessForm(UserCreationForm):
    """Оператор создаёт клиенту доступ в личный кабинет."""
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username',)

    def save(self, client, commit=True):
        user = super().save(commit)
        user.groups.add(AuthGroup.objects.get_or_create(name=CLIENT_GROUP)[0])
        client.user = user
        client.save(update_fields=['user'])
        return user
