"""Совместимость с Django 4.2 LTS (аргумент check) и 5.1+ (аргумент condition)."""
import django
from django.db import models


def check_constraint(condition, name):
    if django.VERSION >= (5, 1):
        return models.CheckConstraint(condition=condition, name=name)
    return models.CheckConstraint(check=condition, name=name)
