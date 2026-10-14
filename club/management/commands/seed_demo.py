from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group as AuthGroup
from django.core.management.base import BaseCommand, CommandError

from club.models import Client, Enrollment, Group, Hall, Section, Subscription, Trainer, Visit
from club.roles import ADMIN_GROUP, OPERATOR_GROUP

User = get_user_model()


class Command(BaseCommand):
    help = 'Создаёт демонстрационные данные'

    def add_arguments(self, parser):
        parser.add_argument('--superuser', help='логин суперпользователя (администратора)')
        parser.add_argument('--password', help='пароль суперпользователя')

    def handle(self, *args, **options):
        if options['superuser']:
            if not options['password']:
                raise CommandError('Для --superuser нужен --password')
            su, _ = User.objects.get_or_create(username=options['superuser'])
            su.is_staff = su.is_superuser = True
            su.set_password(options['password']); su.save()
            self.stdout.write(f'Суперпользователь {su.username} создан/обновлён.')
        admin, _ = User.objects.get_or_create(username='admin_club', defaults={'first_name': 'Администратор'})
        admin.set_password('admin12345'); admin.save()
        admin.groups.add(AuthGroup.objects.get_or_create(name=ADMIN_GROUP)[0])
        op, _ = User.objects.get_or_create(username='operator', defaults={'first_name': 'Оператор'})
        op.set_password('operator12345'); op.save()
        op.groups.add(AuthGroup.objects.get_or_create(name=OPERATOR_GROUP)[0])
        if Client.objects.exists():
            return self.stdout.write('Данные уже есть.')

        swim, gym, box = (Section.objects.create(name=n) for n in ('Плавание', 'Гимнастика', 'Бокс'))
        t1 = Trainer.objects.create(last_name='Петров', first_name='Сергей', patronymic='Иванович')
        t2 = Trainer.objects.create(last_name='Кузнецова', first_name='Анна', patronymic='Павловна')
        t3 = Trainer.objects.create(last_name='Орлов', first_name='Дмитрий', patronymic='Андреевич')
        h1, h2 = Hall.objects.create(number=1, name='Бассейн'), Hall.objects.create(number=2, name='Зал гимнастики')
        h3 = Hall.objects.create(number=3, name='Зал бокса')
        groups = [
            Group.objects.create(section=swim, trainer=t1, hall=h1, weekday=0, start_time=time(9, 0), price=500),
            Group.objects.create(section=swim, trainer=t1, hall=h1, weekday=2, start_time=time(18, 0), duration_min=45, price=450),
            Group.objects.create(section=gym, trainer=t2, hall=h2, weekday=1, start_time=time(10, 0), price=400),
            Group.objects.create(section=gym, trainer=t2, hall=h2, weekday=3, start_time=time(17, 30), duration_min=90, price=600),
            Group.objects.create(section=box, trainer=t3, hall=h3, weekday=0, start_time=time(19, 0), price=550),
            Group.objects.create(section=box, trainer=t3, hall=h3, weekday=4, start_time=time(19, 0), price=550),
        ]
        people = [('Иванов', 'Иван', 'Сергеевич', 'M', date(1995, 3, 14), '+7 900 111-22-01'),
                  ('Смирнова', 'Мария', 'Олеговна', 'F', date(1998, 7, 2), '+7 900 111-22-02'),
                  ('Попов', 'Алексей', 'Игоревич', 'M', date(1990, 11, 23), '+7 900 111-22-03'),
                  ('Соколова', 'Елена', 'Викторовна', 'F', date(2001, 1, 30), '+7 900 111-22-04'),
                  ('Лебедев', 'Никита', 'Андреевич', 'M', date(2003, 5, 9), '+7 900 111-22-05'),
                  ('Козлова', 'Дарья', 'Максимовна', 'F', date(1996, 9, 17), '+7 900 111-22-06'),
                  ('Новиков', 'Артём', 'Денисович', 'M', date(1988, 12, 5), '+7 900 111-22-07'),
                  ('Морозова', 'Ольга', 'Павловна', 'F', date(1993, 4, 21), '+7 900 111-22-08')]
        clients = [Client.objects.create(last_name=a, first_name=b, patronymic=c, gender=d, birth_date=e, phone=f)
                   for a, b, c, d, e, f in people]
        plan = {0: [0, 1, 2], 1: [0, 3], 2: [1, 5], 3: [2, 4, 6], 4: [3, 7], 5: [4, 6, 7, 5]}
        enrolls = []
        for gi, cis in plan.items():
            for ci in cis:
                enrolls.append(Enrollment.objects.create(client=clients[ci], group=groups[gi],
                                                         status='active' if (gi + ci) % 5 else 'booked'))
        Subscription.objects.create(client=clients[0], discount_percent=10,
                                    start_date=date.today() - timedelta(days=60), end_date=date.today() + timedelta(days=30))
        Subscription.objects.create(client=clients[1], discount_percent=5,
                                    start_date=date.today() - timedelta(days=30), end_date=date.today() + timedelta(days=60))
        for i, e in enumerate(enrolls[:8]):
            for k in (14, 7):
                Visit.objects.create(enrollment=e, date=date.today() - timedelta(days=k), attended=(i + k) % 4 != 0)
        self.stdout.write(self.style.SUCCESS(
            'Готово: admin_club/admin12345 (администратор), operator/operator12345 (оператор)'))
