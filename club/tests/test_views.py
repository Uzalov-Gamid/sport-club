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


class CrudTests(BaseTestCase):
    def setUp(self):
        self.login(self.operator)

    def test_create_client(self):
        r = self.client.post(reverse('club:clients_add'), {
            'last_name': 'Иванов', 'first_name': 'Пётр', 'patronymic': '', 'gender': 'M',
            'birth_date': '1999-05-05', 'phone': '+7 900 123-45-67'})
        self.assertRedirects(r, reverse('club:clients'))
        self.assertEqual(Client.objects.get().last_name, 'Иванов')

    def test_invalid_phone_rejected(self):
        r = self.client.post(reverse('club:clients_add'), {
            'last_name': 'Иванов', 'first_name': 'Пётр', 'gender': 'M',
            'birth_date': '1999-05-05', 'phone': 'abc'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Client.objects.count(), 0)

    def test_edit_client(self):
        c = self.make_client()
        self.client.post(reverse('club:clients_edit', args=[c.pk]), {
            'last_name': 'Новая', 'first_name': 'Тест', 'gender': 'F',
            'birth_date': '2000-01-01', 'phone': '+7 900 000-00-00'})
        c.refresh_from_db()
        self.assertEqual((c.last_name, c.gender), ('Новая', 'F'))

    def test_delete_client(self):
        c = self.make_client()
        self.client.post(reverse('club:clients_delete', args=[c.pk]))
        self.assertFalse(Client.objects.exists())

    def test_list_shows_clients(self):
        self.make_client()
        self.assertContains(self.client.get(reverse('club:clients')), 'Клиент1')

    def test_enrollment_into_full_group_shows_error(self):
        for i in range(10):
            Enrollment.objects.create(client=self.make_client(i), group=self.group, status='active')
        extra = self.make_client(99)
        r = self.client.post(reverse('club:enrollments_add'), {
            'client': extra.pk, 'group': self.group.pk, 'status': 'booked', 'created_at': '2026-10-01'})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'уже 10 человек')
        self.assertEqual(Enrollment.objects.count(), 10)

    def test_group_without_duration_gets_60_via_form(self):
        self.client.logout(); self.login(self.admin)
        r = self.client.post(reverse('club:groups_add'), {
            'section': self.swim.pk, 'trainer': self.trainer.pk, 'hall': self.hall.pk,
            'weekday': 3, 'start_time': '15:00', 'duration_min': '', 'price': '300'})
        self.assertRedirects(r, reverse('club:groups'))
        self.assertEqual(Group.objects.get(weekday=3).duration_min, 60)

    def test_protected_trainer_not_deleted(self):
        self.client.logout(); self.login(self.admin)
        self.client.post(reverse('club:trainers_delete', args=[self.trainer.pk]))
        self.assertTrue(type(self.trainer).objects.filter(pk=self.trainer.pk).exists())


class QueryPagesTests(BaseTestCase):
    def setUp(self):
        self.login(self.operator)
        Enrollment.objects.create(client=self.make_client(1, 'M'), group=self.group, status='active')
        Enrollment.objects.create(client=self.make_client(2, 'F'), group=self.group, status='active')

    def test_groups_query_page(self):
        r = self.client.get(reverse('club:q_groups'))
        self.assertContains(r, 'Плавание')
        self.assertEqual(r.context['groups'][0].clients, 2)

    def test_gender_query_page(self):
        r = self.client.get(reverse('club:q_gender'))
        row = next(x for x in r.context['rows'] if x['section'] == 'Плавание')
        self.assertEqual((row['men'], row['women']), (1, 1))

    def test_report_requires_hall(self):
        r = self.client.get(reverse('club:report'))
        self.assertNotIn('schedule', r.context)

    def test_report_content(self):
        r = self.client.get(reverse('club:report'), {'hall': self.hall.pk})
        self.assertContains(r, 'Зал №1')
        self.assertContains(r, 'Дата распечатки')
        self.assertContains(r, 'Понедельник')
        self.assertContains(r, '09:00 – 10:00')

    def test_client_cost_page(self):
        c = Client.objects.first()
        self.assertContains(self.client.get(reverse('club:client_cost', args=[c.pk])), 'Итого')


class TimetableAndDashboardTests(BaseTestCase):
    def test_timetable_page(self):
        self.login(self.operator)
        r = self.client.get(reverse('club:timetable'))
        self.assertContains(r, 'Понедельник')
        self.assertContains(r, '09:00–10:00')

    def test_timetable_requires_login(self):
        self.assertEqual(self.client.get(reverse('club:timetable')).status_code, 302)

    def test_home_dashboard_bars(self):
        Enrollment.objects.create(client=self.make_client(1, 'M'), group=self.group, status='active')
        Enrollment.objects.create(client=self.make_client(2, 'F'), group=self.group, status='active')
        self.login(self.operator)
        r = self.client.get('/')
        self.assertContains(r, 'Заполненность групп')
        row = next(x for x in r.context['by_gender'] if x['section'] == 'Плавание')
        self.assertEqual((row['men_pct'], row['women_pct']), (50, 50))
        self.assertEqual(r.context['fill'][0]['pct'], 20)
