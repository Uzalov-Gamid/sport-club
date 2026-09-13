from django.db import migrations

# Триггеры SQLite (серверная часть)
SQL_UP = [
    # Б) Если продолжительность занятия не указана — 60 минут
    """CREATE TRIGGER trg_group_default_duration_ins AFTER INSERT ON club_group
       WHEN NEW.duration_min IS NULL
       BEGIN UPDATE club_group SET duration_min = 60 WHERE id = NEW.id; END;""",
    """CREATE TRIGGER trg_group_default_duration_upd AFTER UPDATE OF duration_min ON club_group
       WHEN NEW.duration_min IS NULL
       BEGIN UPDATE club_group SET duration_min = 60 WHERE id = NEW.id; END;""",
    # В одну группу не более 10 человек (запись и перенос записи)
    """CREATE TRIGGER trg_enrollment_capacity_ins BEFORE INSERT ON club_enrollment
       WHEN NEW.status IN ('booked', 'active')
       BEGIN
         SELECT RAISE(ABORT, 'В группе уже 10 человек')
         WHERE (SELECT COUNT(*) FROM club_enrollment
                WHERE group_id = NEW.group_id AND status IN ('booked', 'active')) >= 10;
       END;""",
    """CREATE TRIGGER trg_enrollment_capacity_upd BEFORE UPDATE ON club_enrollment
       WHEN NEW.status IN ('booked', 'active')
       BEGIN
         SELECT RAISE(ABORT, 'В группе уже 10 человек')
         WHERE (SELECT COUNT(*) FROM club_enrollment
                WHERE group_id = NEW.group_id AND status IN ('booked', 'active') AND id <> NEW.id) >= 10;
       END;""",
]
TRIGGERS = ['trg_group_default_duration_ins', 'trg_group_default_duration_upd',
            'trg_enrollment_capacity_ins', 'trg_enrollment_capacity_upd']


def create_roles(apps, schema_editor):
    AuthGroup = apps.get_model('auth', 'Group')
    for name in ('Администратор', 'Оператор'):
        AuthGroup.objects.get_or_create(name=name)


class Migration(migrations.Migration):
    dependencies = [('club', '0001_initial'), ('auth', '0012_alter_user_first_name_max_length')]
    operations = [
        migrations.RunSQL(sql=SQL_UP, reverse_sql=[f'DROP TRIGGER IF EXISTS {t};' for t in TRIGGERS]),
        migrations.RunPython(create_roles, migrations.RunPython.noop),
    ]
