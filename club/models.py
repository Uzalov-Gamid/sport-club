from datetime import date, datetime, timedelta

from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.db.models import Q

MAX_GROUP_SIZE = 10
DEFAULT_DURATION = 60
WEEKDAYS = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']


class Client(models.Model):
    class Gender(models.TextChoices):
        MALE = 'M', 'Мужской'
        FEMALE = 'F', 'Женский'

    last_name = models.CharField('Фамилия', max_length=50)
    first_name = models.CharField('Имя', max_length=50)
    patronymic = models.CharField('Отчество', max_length=50, blank=True)
    gender = models.CharField('Пол', max_length=1, choices=Gender.choices)
    birth_date = models.DateField('Дата рождения')
    phone = models.CharField('Телефон', max_length=20,
                             validators=[RegexValidator(r'^[+\d][\d\s()\-]{5,}$', 'Неверный формат телефона')])

    class Meta:
        verbose_name = 'Клиент'
        verbose_name_plural = 'Клиенты'
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return f'{self.last_name} {self.first_name} {self.patronymic}'.strip()


class Section(models.Model):
    name = models.CharField('Вид занятий (секция)', max_length=60, unique=True)

    class Meta:
        verbose_name = 'Секция'
        verbose_name_plural = 'Секции'
        ordering = ['name']

    def __str__(self):
        return self.name


class Trainer(models.Model):
    last_name = models.CharField('Фамилия', max_length=50)
    first_name = models.CharField('Имя', max_length=50)
    patronymic = models.CharField('Отчество', max_length=50, blank=True)
    phone = models.CharField('Телефон', max_length=20, blank=True)

    class Meta:
        verbose_name = 'Тренер'
        verbose_name_plural = 'Тренеры'
        ordering = ['last_name', 'first_name']

    def __str__(self):
        initials = ''.join(f'{x[0]}.' for x in (self.first_name, self.patronymic) if x)
        return f'{self.last_name} {initials}'.strip()


class Hall(models.Model):
    number = models.PositiveSmallIntegerField('Номер зала', unique=True)
    name = models.CharField('Название', max_length=60, blank=True)

    class Meta:
        verbose_name = 'Зал'
        verbose_name_plural = 'Залы'
        ordering = ['number']

    def __str__(self):
        return f'Зал №{self.number}'
