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
