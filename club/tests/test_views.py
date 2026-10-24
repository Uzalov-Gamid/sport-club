from datetime import date

from django.contrib.auth import get_user_model
from django.urls import reverse

from club.models import Client, Enrollment, Group, Section, Subscription, Visit

from .base import BaseTestCase

User = get_user_model()
CLIENT_DATA = {'last_name': 'Иванов', 'first_name': 'Пётр', 'patronymic': '', 'gender': 'M',
               'birth_date': '1999-05-05', 'phone': '+7 900 123-45-67'}


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

    def test_operator_menu_has_no_catalog(self):
        self.login(self.operator)
        r = self.client.get(reverse('club:home'))
        self.assertContains(r, 'Клиенты')
        self.assertNotContains(r, 'Справочники')

    def test_admin_menu_has_catalog(self):
        self.login(self.admin)
        self.assertContains(self.client.get(reverse('club:home')), 'Справочники')

    def test_operator_cannot_open_catalog(self):
        self.login(self.operator)
        self.assertEqual(self.client.get(reverse('club:catalog')).status_code, 403)
        self.assertEqual(self.client.get(reverse('club:catalog') + '?tab=users').status_code, 403)

    def test_admin_can_open_catalog_tabs(self):
        self.login(self.admin)
        for tab in ('sections', 'trainers', 'halls', 'users'):
            self.assertEqual(self.client.get(reverse('club:catalog'), {'tab': tab}).status_code, 200, tab)

    def test_admin_adds_operator_who_can_log_in(self):
        self.login(self.admin)
        r = self.client.post(reverse('club:user_add'), {
            'username': 'newop', 'first_name': 'Нов', 'last_name': 'Оператор',
            'password1': 'Str0ngPass!77', 'password2': 'Str0ngPass!77'})
        self.assertEqual(r.status_code, 302)
        u = User.objects.get(username='newop')
        self.assertTrue(u.groups.filter(name='Оператор').exists())
        self.assertFalse(u.is_superuser)
        self.client.logout()
        self.assertTrue(self.client.login(username='newop', password='Str0ngPass!77'))

    def test_operator_cannot_add_users(self):
        self.login(self.operator)
        self.assertEqual(self.client.post(reverse('club:user_add'), {'username': 'x'}).status_code, 403)
        self.assertFalse(User.objects.filter(username='x').exists())

    def test_get_not_allowed_for_actions(self):
        self.login(self.operator)
        self.assertEqual(self.client.get(reverse('club:client_add')).status_code, 405)


class ClientTests(BaseTestCase):
    def setUp(self):
        self.login(self.operator)

    def test_create_client_opens_card(self):
        r = self.client.post(reverse('club:client_add'), CLIENT_DATA)
        c = Client.objects.get()
        self.assertRedirects(r, reverse('club:client', args=[c.pk]))
        self.assertEqual(c.last_name, 'Иванов')

    def test_invalid_phone_rejected_with_message(self):
        r = self.client.post(reverse('club:client_add'), dict(CLIENT_DATA, phone='abc'), follow=True)
        self.assertEqual(Client.objects.count(), 0)
        self.assertContains(r, 'Неверный формат телефона')

    def test_edit_client(self):
        c = self.make_client()
        self.client.post(reverse('club:client_edit', args=[c.pk]), dict(CLIENT_DATA, last_name='Новая', gender='F'))
        c.refresh_from_db()
        self.assertEqual((c.last_name, c.gender), ('Новая', 'F'))

    def test_delete_client(self):
        c = self.make_client()
        self.client.post(reverse('club:client_delete', args=[c.pk]))
        self.assertFalse(Client.objects.exists())

    def test_list_and_search(self):
        self.make_client(1); self.make_client(2)
        r = self.client.get(reverse('club:clients'))
        self.assertContains(r, 'Клиент1')
        r = self.client.get(reverse('club:clients'), {'q': 'Клиент2'})
        self.assertContains(r, 'Клиент2')
        self.assertNotContains(r, 'Клиент1')

    def test_card_shows_enrollment_and_discount(self):
        c = self.make_client()
        Enrollment.objects.create(client=c, group=self.group, status='active')
        Subscription.objects.create(client=c, discount_percent=7, start_date=date(2020, 1, 1), end_date=date(2099, 1, 1))
        r = self.client.get(reverse('club:client', args=[c.pk]))
        self.assertContains(r, 'Плавание')
        self.assertContains(r, '−7%')


class EnrollmentTests(BaseTestCase):
    def setUp(self):
        self.login(self.operator)

    def test_enroll_from_client_card(self):
        c = self.make_client()
        r = self.client.post(reverse('club:client_enroll', args=[c.pk]), {'group': self.group.pk, 'status': 'active'})
        self.assertRedirects(r, reverse('club:client', args=[c.pk]))
        self.assertEqual(Enrollment.objects.get().status, 'active')

    def test_enroll_from_group_card(self):
        c = self.make_client()
        self.client.post(reverse('club:group_enroll', args=[self.group.pk]), {'client': c.pk, 'status': 'booked'})
        self.assertEqual(Enrollment.objects.get().status, 'booked')

    def test_full_group_rejects_eleventh(self):
        for i in range(10):
            Enrollment.objects.create(client=self.make_client(i), group=self.group, status='active')
        extra = self.make_client(99)
        r = self.client.post(reverse('club:client_enroll', args=[extra.pk]),
                             {'group': self.group.pk, 'status': 'active'}, follow=True)
        self.assertContains(r, 'уже 10 человек')
        self.assertEqual(Enrollment.objects.count(), 10)

    def test_duplicate_enrollment_rejected(self):
        c = self.make_client()
        Enrollment.objects.create(client=c, group=self.group, status='active')
        r = self.client.post(reverse('club:client_enroll', args=[c.pk]),
                             {'group': self.group.pk, 'status': 'active'}, follow=True)
        self.assertContains(r, 'уже записан')
        self.assertEqual(Enrollment.objects.count(), 1)

    def test_cancel_and_confirm(self):
        e = Enrollment.objects.create(client=self.make_client(), group=self.group, status='booked')
        self.client.post(reverse('club:enrollment_status', args=[e.pk]), {'status': 'active'})
        e.refresh_from_db(); self.assertEqual(e.status, 'active')
        self.client.post(reverse('club:enrollment_status', args=[e.pk]), {'status': 'cancelled'})
        e.refresh_from_db(); self.assertEqual(e.status, 'cancelled')

    def test_restore_into_full_group_rejected(self):
        for i in range(10):
            Enrollment.objects.create(client=self.make_client(i), group=self.group, status='active')
        e = Enrollment.objects.create(client=self.make_client(50), group=self.group, status='cancelled')
        self.client.post(reverse('club:enrollment_status', args=[e.pk]), {'status': 'active'})
        e.refresh_from_db(); self.assertEqual(e.status, 'cancelled')

    def test_bad_status_404(self):
        e = Enrollment.objects.create(client=self.make_client(), group=self.group)
        self.assertEqual(self.client.post(reverse('club:enrollment_status', args=[e.pk]), {'status': 'x'}).status_code, 404)

    def test_delete_enrollment(self):
        e = Enrollment.objects.create(client=self.make_client(), group=self.group)
        self.client.post(reverse('club:enrollment_delete', args=[e.pk]))
        self.assertFalse(Enrollment.objects.exists())

    def test_next_redirect_only_to_own_site(self):
        e = Enrollment.objects.create(client=self.make_client(), group=self.group)
        r = self.client.post(reverse('club:enrollment_delete', args=[e.pk]), {'next': 'https://evil.example/'})
        self.assertRedirects(r, reverse('club:client', args=[e.client_id]), fetch_redirect_response=False)


class VisitTests(BaseTestCase):
    def setUp(self):
        self.login(self.operator)
        self.e = Enrollment.objects.create(client=self.make_client(), group=self.group, status='active')

    def test_quick_mark_present_then_absent(self):
        url = reverse('club:visit_mark', args=[self.e.pk])
        self.client.post(url, {'date': '2026-10-05', 'attended': '1'})
        self.assertTrue(Visit.objects.get().attended)
        self.client.post(url, {'date': '2026-10-05', 'attended': '0'})
        self.assertEqual(Visit.objects.count(), 1)
        self.assertFalse(Visit.objects.get().attended)

    def test_group_attendance_sheet(self):
        e2 = Enrollment.objects.create(client=self.make_client(2), group=self.group, status='active')
        self.client.post(reverse('club:group_attendance', args=[self.group.pk]),
                         {'date': '2026-10-05', 'present': [str(self.e.pk)]})
        self.assertTrue(Visit.objects.get(enrollment=self.e).attended)
        self.assertFalse(Visit.objects.get(enrollment=e2).attended)

    def test_group_card_shows_participants(self):
        r = self.client.get(reverse('club:group', args=[self.group.pk]), {'date': '2026-10-05'})
        self.assertContains(r, 'Клиент1')
        self.assertContains(r, '2026')

    def test_visit_clear(self):
        Visit.objects.create(enrollment=self.e, date=date(2026, 10, 5))
        self.client.post(reverse('club:visit_clear', args=[self.e.pk]), {'date': '2026-10-05'})
        self.assertFalse(Visit.objects.exists())


class SubscriptionTests(BaseTestCase):
    def setUp(self):
        self.login(self.operator)
        self.c = self.make_client()

    def test_add_subscription(self):
        self.client.post(reverse('club:subscription_add', args=[self.c.pk]),
                         {'discount_percent': 5, 'start_date': '2026-10-01', 'end_date': '2026-12-31'})
        self.assertEqual(Subscription.objects.get().discount_percent, 5)

    def test_discount_out_of_range_rejected(self):
        for percent in (2, 11):
            self.client.post(reverse('club:subscription_add', args=[self.c.pk]),
                             {'discount_percent': percent, 'start_date': '2026-10-01', 'end_date': '2026-12-31'})
        self.assertFalse(Subscription.objects.exists())

    def test_end_before_start_rejected(self):
        self.client.post(reverse('club:subscription_add', args=[self.c.pk]),
                         {'discount_percent': 5, 'start_date': '2026-12-01', 'end_date': '2026-10-01'})
        self.assertFalse(Subscription.objects.exists())

    def test_delete_subscription(self):
        s = Subscription.objects.create(client=self.c, discount_percent=5, start_date=date(2026, 1, 1), end_date=date(2026, 2, 1))
        self.client.post(reverse('club:subscription_delete', args=[s.pk]))
        self.assertFalse(Subscription.objects.exists())

    def test_cost_block_with_discount(self):
        e = Enrollment.objects.create(client=self.c, group=self.group, status='active')
        Visit.objects.create(enrollment=e, date=date(2026, 10, 5), attended=True)
        Subscription.objects.create(client=self.c, discount_percent=10, start_date=date(2026, 10, 1), end_date=date(2026, 12, 1))
        r = self.client.get(reverse('club:client', args=[self.c.pk]), {'date_from': '2026-10-01', 'date_to': '2026-10-31'})
        self.assertContains(r, '450.00')


class GroupAndCatalogTests(BaseTestCase):
    def test_admin_creates_group_without_duration_gets_60(self):
        self.login(self.admin)
        r = self.client.post(reverse('club:group_add'), {
            'section': self.swim.pk, 'trainer': self.trainer.pk, 'hall': self.hall.pk,
            'weekday': 3, 'start_time': '15:00', 'duration_min': '', 'price': '300'})
        g = Group.objects.get(weekday=3)
        self.assertRedirects(r, reverse('club:group', args=[g.pk]))
        self.assertEqual(g.duration_min, 60)

    def test_operator_cannot_manage_groups(self):
        self.login(self.operator)
        self.assertEqual(self.client.post(reverse('club:group_delete', args=[self.group.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse('club:group_add'), {}).status_code, 403)
        self.assertTrue(Group.objects.filter(pk=self.group.pk).exists())

    def test_admin_edits_and_deletes_group(self):
        self.login(self.admin)
        self.client.post(reverse('club:group_edit', args=[self.group.pk]), {
            'section': self.swim.pk, 'trainer': self.trainer.pk, 'hall': self.hall.pk,
            'weekday': 1, 'start_time': '10:00', 'duration_min': '90', 'price': '700'})
        self.group.refresh_from_db()
        self.assertEqual((self.group.weekday, self.group.duration_min), (1, 90))
        self.client.post(reverse('club:group_delete', args=[self.group.pk]))
        self.assertFalse(Group.objects.exists())

    def test_catalog_add_edit_delete_section(self):
        self.login(self.admin)
        self.client.post(reverse('club:catalog_add', args=['sections']), {'name': 'Йога'})
        s = Section.objects.get(name='Йога')
        self.client.post(reverse('club:catalog_edit', args=['sections', s.pk]), {'name': 'Пилатес'})
        s.refresh_from_db(); self.assertEqual(s.name, 'Пилатес')
        self.client.post(reverse('club:catalog_delete', args=['sections', s.pk]))
        self.assertFalse(Section.objects.filter(pk=s.pk).exists())

    def test_protected_trainer_not_deleted(self):
        self.login(self.admin)
        r = self.client.post(reverse('club:catalog_delete', args=['trainers', self.trainer.pk]), follow=True)
        self.assertTrue(type(self.trainer).objects.filter(pk=self.trainer.pk).exists())
        self.assertContains(r, 'Нельзя удалить')

    def test_unknown_catalog_kind_404(self):
        self.login(self.admin)
        self.assertEqual(self.client.post(reverse('club:catalog_add', args=['nothing']), {}).status_code, 404)


class ReportsTests(BaseTestCase):
    def setUp(self):
        self.login(self.operator)
        Enrollment.objects.create(client=self.make_client(1, 'M'), group=self.group, status='active')
        Enrollment.objects.create(client=self.make_client(2, 'F'), group=self.group, status='active')

    def test_groups_tab(self):
        r = self.client.get(reverse('club:reports'), {'tab': 'groups'})
        self.assertContains(r, 'Плавание')
        self.assertEqual(r.context['groups'][0].clients, 2)

    def test_gender_tab(self):
        r = self.client.get(reverse('club:reports'), {'tab': 'gender'})
        row = next(x for x in r.context['rows'] if x['section'] == 'Плавание')
        self.assertEqual((row['men'], row['women']), (1, 1))

    def test_hall_tab_content(self):
        r = self.client.get(reverse('club:reports'), {'tab': 'hall', 'hall': self.hall.pk})
        self.assertContains(r, 'Зал №1')
        self.assertContains(r, 'Дата распечатки')
        self.assertContains(r, 'Понедельник')
        self.assertContains(r, '09:00 – 10:00')

    def test_unknown_tab_falls_back(self):
        self.assertEqual(self.client.get(reverse('club:reports'), {'tab': 'zzz'}).context['tab'], 'groups')


class TimetableAndDashboardTests(BaseTestCase):
    def test_timetable_page_links_to_group(self):
        self.login(self.operator)
        r = self.client.get(reverse('club:timetable'))
        self.assertContains(r, '09:00–10:00')
        self.assertContains(r, reverse('club:group', args=[self.group.pk]))

    def test_timetable_requires_login(self):
        self.assertEqual(self.client.get(reverse('club:timetable')).status_code, 302)

    def test_home_dashboard(self):
        Enrollment.objects.create(client=self.make_client(1, 'M'), group=self.group, status='active')
        Enrollment.objects.create(client=self.make_client(2, 'F'), group=self.group, status='active')
        self.login(self.operator)
        r = self.client.get('/')
        self.assertContains(r, 'Заполненность групп')
        row = next(x for x in r.context['by_gender'] if x['section'] == 'Плавание')
        self.assertEqual((row['men_pct'], row['women_pct']), (50, 50))
        self.assertEqual(r.context['fill'][0]['pct'], 20)

    def test_home_lists_todays_groups(self):
        g = self.make_group(weekday=date.today().weekday(), start_time=__import__('datetime').time(18, 30))
        self.login(self.operator)
        r = self.client.get('/')
        self.assertIn(g, list(r.context['todays']))
