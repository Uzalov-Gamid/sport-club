from datetime import date, datetime, timedelta

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.db.models import Q

from .compat import check_constraint

MAX_GROUP_SIZE = 10
DEFAULT_DURATION = 60
WEEKDAYS = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
WEEKDAYS_SHORT = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']


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
    email = models.EmailField('E-mail', blank=True)
    note = models.TextField('Заметка', blank=True, help_text='Например: противопоказания, пожелания, откуда узнал о клубе')
    joined = models.DateField('Клиент с', default=date.today, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, verbose_name='Учётная запись', null=True, blank=True,
                                on_delete=models.SET_NULL, related_name='client_profile', editable=False)

    class Meta:
        verbose_name = 'Клиент'
        verbose_name_plural = 'Клиенты'
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return f'{self.last_name} {self.first_name} {self.patronymic}'.strip()

    @property
    def age(self):
        today = date.today()
        return today.year - self.birth_date.year - ((today.month, today.day) < (self.birth_date.month, self.birth_date.day))


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


class Group(models.Model):
    """Группа занятий: секция + тренер + зал + день недели + время начала."""
    section = models.ForeignKey(Section, verbose_name='Секция', on_delete=models.PROTECT, related_name='groups')
    trainer = models.ForeignKey(Trainer, verbose_name='Тренер', on_delete=models.PROTECT, related_name='groups')
    hall = models.ForeignKey(Hall, verbose_name='Зал', on_delete=models.PROTECT, related_name='groups')
    weekday = models.PositiveSmallIntegerField('День недели', choices=list(enumerate(WEEKDAYS)))
    start_time = models.TimeField('Начало')
    # NULL допустим: при вставке без значения триггер БД устанавливает 60 минут
    duration_min = models.PositiveSmallIntegerField('Длительность, мин', null=True, blank=True,
                                                    validators=[MinValueValidator(10), MaxValueValidator(300)])
    price = models.DecimalField('Стоимость занятия, ₽', max_digits=8, decimal_places=2,
                                validators=[MinValueValidator(0)])

    class Meta:
        verbose_name = 'Группа'
        verbose_name_plural = 'Группы'
        ordering = ['weekday', 'start_time']

    @property
    def weekday_short(self):
        return WEEKDAYS_SHORT[self.weekday]

    def __str__(self):
        return f'{self.section}, {self.trainer}, {self.weekday_short} {self.start_time:%H:%M}'

    @property
    def end_time(self):
        minutes = self.duration_min or DEFAULT_DURATION
        return (datetime.combine(date.today(), self.start_time) + timedelta(minutes=minutes)).time()

    def active_count(self):
        return self.enrollments.filter(status__in=Enrollment.OCCUPYING).count()


class Enrollment(models.Model):
    """Запись клиента в группу (предварительная или действующая)."""
    class Status(models.TextChoices):
        BOOKED = 'booked', 'Предварительная запись'
        ACTIVE = 'active', 'Занимается'
        CANCELLED = 'cancelled', 'Отменена'

    OCCUPYING = ('booked', 'active')

    client = models.ForeignKey(Client, verbose_name='Клиент', on_delete=models.CASCADE, related_name='enrollments')
    group = models.ForeignKey(Group, verbose_name='Группа', on_delete=models.CASCADE, related_name='enrollments')
    status = models.CharField('Статус', max_length=10, choices=Status.choices, default=Status.BOOKED)
    created_at = models.DateField('Дата записи', default=date.today)

    class Meta:
        verbose_name = 'Запись на занятия'
        verbose_name_plural = 'Записи на занятия'
        ordering = ['-created_at']
        constraints = [models.UniqueConstraint(fields=['client', 'group'], name='uniq_client_group')]

    def __str__(self):
        return f'{self.client} → {self.group}'

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.status in self.OCCUPYING and self.group_id:
            taken = Enrollment.objects.filter(group_id=self.group_id, status__in=self.OCCUPYING)\
                .exclude(pk=self.pk).count()
            if taken >= MAX_GROUP_SIZE:
                raise ValidationError(f'В группе уже {MAX_GROUP_SIZE} человек — запись невозможна.')


class Subscription(models.Model):
    client = models.ForeignKey(Client, verbose_name='Клиент', on_delete=models.CASCADE, related_name='subscriptions')
    discount_percent = models.PositiveSmallIntegerField(
        'Скидка, %', validators=[MinValueValidator(3), MaxValueValidator(10)])
    start_date = models.DateField('Начало')
    end_date = models.DateField('Окончание')

    class Meta:
        verbose_name = 'Абонемент'
        verbose_name_plural = 'Абонементы'
        ordering = ['-start_date']
        constraints = [
            check_constraint(Q(discount_percent__gte=3, discount_percent__lte=10), 'discount_3_10'),
            check_constraint(Q(end_date__gte=models.F('start_date')), 'sub_dates'),
        ]

    def __str__(self):
        return f'{self.client}: −{self.discount_percent}% ({self.start_date:%d.%m.%Y}–{self.end_date:%d.%m.%Y})'

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError('Дата окончания раньше даты начала.')


class Visit(models.Model):
    enrollment = models.ForeignKey(Enrollment, verbose_name='Запись', on_delete=models.CASCADE, related_name='visits')
    date = models.DateField('Дата занятия', default=date.today)
    attended = models.BooleanField('Присутствовал', default=True)
    self_marked = models.BooleanField('Отметил сам клиент', default=False)

    class Meta:
        verbose_name = 'Посещение'
        verbose_name_plural = 'Посещения'
        ordering = ['-date']
        constraints = [models.UniqueConstraint(fields=['enrollment', 'date'], name='uniq_visit_day')]

    def __str__(self):
        return f'{self.enrollment.client}, {self.date:%d.%m.%Y}'
