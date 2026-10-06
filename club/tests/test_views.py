from django.contrib.auth import get_user_model
from django.urls import reverse

from club.models import Client, Enrollment, Group

from .base import BaseTestCase

User = get_user_model()


class AuthRolesTests(BaseTestCase):
    def test_anonymous_redirected(self):
        self.assertRedirects(self.client.get(reverse('club:home')), '/login/?next=/')

    def test_login_with_credentials(self):
        r = self.client.post(reverse('login'), {'username': 'op', 'password': 'pass12345'})
        self.assertRedirects(r, reverse('club:home'))

    def test_wrong_password_rejected(self):
        r = self.client.post(reverse('login'), {'username': 'op', 'password': 'bad'})
        self.assertEqual(r.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_user_without_role_forbidden(self):
        self.login(self.nobody)
        self.assertEqual(self.client.get(reverse('club:home')).status_code, 403)

    def test_operator_sees_menu_without_admin_tiles(self):
        self.login(self.operator)
        r = self.client.get(reverse('club:home'))
        self.assertContains(r, 'Клиенты')
        self.assertNotContains(r, 'Тренеры')

    def test_admin_sees_admin_tiles(self):
        self.login(self.admin)
        self.assertContains(self.client.get(reverse('club:home')), 'Тренеры')

    def test_operator_cannot_open_dictionaries_or_users(self):
        self.login(self.operator)
        for name in ('groups', 'trainers', 'sections', 'halls', 'users'):
            self.assertEqual(self.client.get(reverse(f'club:{name}')).status_code, 403, name)

    def test_admin_can_open_dictionaries(self):
        self.login(self.admin)
        for name in ('groups', 'trainers', 'sections', 'halls', 'users'):
            self.assertEqual(self.client.get(reverse(f'club:{name}')).status_code, 200, name)

    def test_admin_adds_operator_who_can_log_in(self):
        self.login(self.admin)
        r = self.client.post(reverse('club:users'), {
            'username': 'newop', 'first_name': 'Нов', 'last_name': 'Оператор',
            'password1': 'Str0ngPass!77', 'password2': 'Str0ngPass!77'})
        self.assertRedirects(r, reverse('club:users'))
        u = User.objects.get(username='newop')
        self.assertTrue(u.groups.filter(name='Оператор').exists())
        self.assertFalse(u.is_superuser)
        self.client.logout()
        self.assertTrue(self.client.login(username='newop', password='Str0ngPass!77'))

    def test_operator_cannot_add_users(self):
        self.login(self.operator)
        r = self.client.post(reverse('club:users'), {'username': 'x'})
        self.assertEqual(r.status_code, 403)
