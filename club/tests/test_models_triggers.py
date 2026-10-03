from datetime import date, time

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from club.models import DEFAULT_DURATION, Enrollment, Group, Subscription

from .base import BaseTestCase


class DurationTriggerTests(BaseTestCase):
    def test_trigger_sets_60_when_duration_missing(self):
        g = self.make_group(duration_min=None, weekday=2)
        g.refresh_from_db()
        self.assertEqual(g.duration_min, 60)

    def test_explicit_duration_kept(self):
        g = self.make_group(duration_min=45, weekday=3)
        g.refresh_from_db()
        self.assertEqual(g.duration_min, 45)

    def test_trigger_on_update_to_null(self):
        g = self.make_group(duration_min=90, weekday=4)
        Group.objects.filter(pk=g.pk).update(duration_min=None)
        g.refresh_from_db()
        self.assertEqual(g.duration_min, 60)

    def test_end_time_uses_default(self):
        g = Group(section=self.swim, trainer=self.trainer, hall=self.hall, weekday=1,
                  start_time=time(10, 0), duration_min=None, price=1)
        self.assertEqual(g.end_time, time(10, 0).replace(hour=11))
        self.assertEqual(DEFAULT_DURATION, 60)


class CapacityTriggerTests(BaseTestCase):
    def fill(self, n):
        for i in range(n):
            Enrollment.objects.create(client=self.make_client(i), group=self.group, status='active')

    def test_ten_allowed(self):
        self.fill(10)
        self.assertEqual(self.group.active_count(), 10)

    def test_eleventh_rejected_by_db_trigger(self):
        self.fill(10)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Enrollment.objects.create(client=self.make_client(99), group=self.group)

    def test_cancelled_does_not_occupy_place(self):
        self.fill(9)
        Enrollment.objects.create(client=self.make_client(50), group=self.group, status='cancelled')
        Enrollment.objects.create(client=self.make_client(51), group=self.group, status='active')
        self.assertEqual(self.group.active_count(), 10)

    def test_reactivating_into_full_group_rejected(self):
        self.fill(10)
        e = Enrollment.objects.create(client=self.make_client(60), group=self.group, status='cancelled')
        e.status = 'active'
        with self.assertRaises(IntegrityError), transaction.atomic():
            e.save()

    def test_model_clean_gives_friendly_error(self):
        self.fill(10)
        e = Enrollment(client=self.make_client(70), group=self.group, status='booked')
        with self.assertRaises(ValidationError):
            e.clean()

    def test_same_client_twice_in_group_rejected(self):
        c = self.make_client(1)
        Enrollment.objects.create(client=c, group=self.group)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Enrollment.objects.create(client=c, group=self.group)


class SubscriptionConstraintTests(BaseTestCase):
    def make(self, percent, start=date(2026, 1, 1), end=date(2026, 12, 31)):
        return Subscription.objects.create(client=self.make_client(), discount_percent=percent,
                                           start_date=start, end_date=end)

    def test_discount_bounds_ok(self):
        self.make(3); self.make(10)

    def test_discount_below_3_rejected_by_db(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make(2)

    def test_discount_above_10_rejected_by_db(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make(11)

    def test_end_before_start_rejected_by_db(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make(5, start=date(2026, 5, 1), end=date(2026, 4, 1))

    def test_validator_rejects_out_of_range(self):
        s = Subscription(client=self.make_client(), discount_percent=15,
                         start_date=date(2026, 1, 1), end_date=date(2026, 2, 1))
        with self.assertRaises(ValidationError):
            s.full_clean()


class StrTests(BaseTestCase):
    def test_trainer_str(self):
        self.assertEqual(str(self.trainer), 'Петров С.И.')

    def test_hall_str(self):
        self.assertEqual(str(self.hall), 'Зал №1')

    def test_group_str(self):
        self.assertIn('Плавание', str(self.group))
