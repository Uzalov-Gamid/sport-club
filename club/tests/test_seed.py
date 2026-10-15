from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command

from django.test import TestCase

from club.models import Client
from club.roles import is_admin

User = get_user_model()


class SeedCommandTests(TestCase):
    def test_seed_creates_demo_data_and_roles(self):
        call_command('seed_demo', stdout=open('/dev/null', 'w'))
        self.assertTrue(Client.objects.exists())
        self.assertTrue(is_admin(User.objects.get(username='admin_club')))
        self.assertFalse(is_admin(User.objects.get(username='operator')))

    def test_seed_is_idempotent(self):
        call_command('seed_demo', stdout=open('/dev/null', 'w'))
        n = Client.objects.count()
        call_command('seed_demo', stdout=open('/dev/null', 'w'))
        self.assertEqual(Client.objects.count(), n)

    def test_superuser_option_creates_working_admin(self):
        call_command('seed_demo', superuser='root1', password='x-Pass-1', stdout=open('/dev/null', 'w'))
        u = User.objects.get(username='root1')
        self.assertTrue(u.is_superuser and is_admin(u))
        self.assertTrue(self.client.login(username='root1', password='x-Pass-1'))

    def test_superuser_requires_password(self):
        with self.assertRaises(CommandError):
            call_command('seed_demo', superuser='root2')

    def test_home_shows_stats_and_role(self):
        call_command('seed_demo', stdout=open('/dev/null', 'w'))
        self.client.login(username='operator', password='operator12345')
        r = self.client.get('/')
        self.assertContains(r, 'Занимаются сейчас')
        self.assertContains(r, 'Оператор')
