from datetime import date, timedelta
from decimal import Decimal

from club import services
from club.models import Enrollment, Subscription, Visit

from .base import BaseTestCase


class QueryTests(BaseTestCase):
    def setUp(self):
        self.g2 = self.make_group(section=self.box, weekday=2)
        self.m1, self.m2 = self.make_client(1, 'M'), self.make_client(2, 'M')
        self.f1 = self.make_client(3, 'F')
        for c in (self.m1, self.m2, self.f1):
            Enrollment.objects.create(client=c, group=self.group, status='active')
        Enrollment.objects.create(client=self.m1, group=self.g2, status='active')
        Enrollment.objects.create(client=self.make_client(4), group=self.g2, status='booked')
        Enrollment.objects.create(client=self.make_client(5), group=self.g2, status='cancelled')

    def test_group_counts_only_active(self):
        counts = {g.pk: g.clients for g in services.groups_with_client_counts()}
        self.assertEqual(counts[self.group.pk], 3)
        self.assertEqual(counts[self.g2.pk], 1)

    def test_empty_group_has_zero(self):
        g3 = self.make_group(weekday=5)
        counts = {g.pk: g.clients for g in services.groups_with_client_counts()}
        self.assertEqual(counts[g3.pk], 0)

    def test_gender_by_section(self):
        rows = {r['section']: r for r in services.clients_by_section_and_gender()}
        self.assertEqual((rows['Плавание']['men'], rows['Плавание']['women']), (2, 1))
        self.assertEqual((rows['Бокс']['men'], rows['Бокс']['women']), (1, 0))

    def test_client_in_two_groups_of_one_section_counted_once(self):
        g3 = self.make_group(weekday=6)
        Enrollment.objects.create(client=self.m1, group=g3, status='active')
        rows = {r['section']: r for r in services.clients_by_section_and_gender()}
        self.assertEqual(rows['Плавание']['men'], 2)


class CostTests(BaseTestCase):
    def setUp(self):
        self.c = self.make_client()
        self.e = Enrollment.objects.create(client=self.c, group=self.group, status='active')
        self.today = date.today()

    def visit(self, days_ago, attended=True):
        return Visit.objects.create(enrollment=self.e, date=self.today - timedelta(days=days_ago), attended=attended)

    def test_no_subscription_full_price(self):
        self.assertEqual(services.visit_cost(self.visit(1)), Decimal('500.00'))

    def test_discount_applied(self):
        Subscription.objects.create(client=self.c, discount_percent=10,
                                    start_date=self.today - timedelta(days=30), end_date=self.today + timedelta(days=30))
        self.assertEqual(services.visit_cost(self.visit(1)), Decimal('450.00'))

    def test_expired_subscription_ignored(self):
        Subscription.objects.create(client=self.c, discount_percent=10,
                                    start_date=self.today - timedelta(days=90), end_date=self.today - timedelta(days=60))
        self.assertEqual(services.visit_cost(self.visit(1)), Decimal('500.00'))

    def test_missed_visit_free(self):
        self.assertEqual(services.visit_cost(self.visit(1, attended=False)), Decimal('0.00'))

    def test_total_and_period(self):
        self.visit(10); self.visit(5)
        rows, total = services.client_cost(self.c)
        self.assertEqual((len(rows), total), (2, Decimal('1000.00')))
        rows, total = services.client_cost(self.c, date_from=self.today - timedelta(days=6))
        self.assertEqual((len(rows), total), (1, Decimal('500.00')))

    def test_best_discount_chosen(self):
        for p in (3, 7):
            Subscription.objects.create(client=self.c, discount_percent=p,
                                        start_date=self.today - timedelta(days=5), end_date=self.today + timedelta(days=5))
        self.assertEqual(services.discount_on(self.c, self.today), 7)


class ScheduleTests(BaseTestCase):
    def test_grouped_by_weekday_sorted(self):
        from datetime import time
        self.make_group(weekday=0, start_time=time(8, 0))
        self.make_group(weekday=2, start_time=time(12, 0), duration_min=90)
        sched = services.hall_schedule(self.hall)
        self.assertEqual([d for d, _ in sched], ['Понедельник', 'Среда'])
        self.assertEqual(sched[0][1][0][0], time(8, 0))
        self.assertEqual(sched[1][1][0][1], time(13, 30))

    def test_empty_hall(self):
        from club.models import Hall
        self.assertEqual(services.hall_schedule(Hall.objects.create(number=9)), [])


class TimetableTests(BaseTestCase):
    def test_week_has_seven_days_with_groups_in_time_order(self):
        from datetime import time
        self.make_group(weekday=0, start_time=time(8, 0))
        days = services.week_timetable()
        self.assertEqual(len(days), 7)
        self.assertEqual([g.start_time for g in days[0]['groups']], [time(8, 0), time(9, 0)])
        self.assertEqual(days[3]['groups'], [])

    def test_group_color_depends_on_section(self):
        days = services.week_timetable()
        self.assertEqual(days[0]['groups'][0].color, self.swim.pk % 6)
