from django.contrib import admin

from . import models

for m in (models.Client, models.Section, models.Trainer, models.Hall, models.Group,
          models.Enrollment, models.Subscription, models.Visit):
    admin.site.register(m)
