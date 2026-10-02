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
