from datetime import date, time

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group as AuthGroup
from django.test import TestCase

from club.models import Client, Enrollment, Group, Hall, Section, Trainer
from club.roles import ADMIN_GROUP, OPERATOR_GROUP

User = get_user_model()


class BaseTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user('adm', password='pass12345')
        cls.admin.groups.add(AuthGroup.objects.get(name=ADMIN_GROUP))
        cls.operator = User.objects.create_user('op', password='pass12345')
        cls.operator.groups.add(AuthGroup.objects.get(name=OPERATOR_GROUP))
        cls.nobody = User.objects.create_user('nobody', password='pass12345')
        cls.swim = Section.objects.create(name='Плавание')
        cls.box = Section.objects.create(name='Бокс')
        cls.trainer = Trainer.objects.create(last_name='Петров', first_name='Сергей', patronymic='Иванович')
        cls.hall = Hall.objects.create(number=1, name='Бассейн')
        cls.group = cls.make_group()

    @classmethod
    def make_group(cls, **kw):
        data = dict(section=cls.swim, trainer=cls.trainer, hall=cls.hall, weekday=0,
                    start_time=time(9, 0), duration_min=60, price=500)
        data.update(kw)
        return Group.objects.create(**data)

    @classmethod
    def make_client(cls, n=1, gender='M'):
        return Client.objects.create(last_name=f'Клиент{n}', first_name='Тест', gender=gender,
                                     birth_date=date(2000, 1, 1), phone='+7 900 000-00-00')

    def login(self, user):
        self.client.login(username=user.username, password='pass12345')
