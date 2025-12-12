from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("peachjam", "0261_judgment_flynote_stars"),
    ]

    operations = [
        migrations.RunSQL(
            """
            -- Remove M2M references for duplicates
            DELETE
            FROM peachjam_timelineevent_subject_works
            WHERE timelineevent_id IN (SELECT id
                                       FROM peachjam_timelineevent t
                                       WHERE t.email_alert_sent_at IS NULL
                                         AND t.id NOT IN (SELECT MIN(id)
                                                          FROM peachjam_timelineevent
                                                          WHERE email_alert_sent_at IS NULL
                                                          GROUP BY user_following_id, event_type));

            -- Delete duplicate TimelineEvent rows
            DELETE
            FROM peachjam_timelineevent t
            WHERE t.email_alert_sent_at IS NULL
              AND t.id NOT IN (SELECT MIN(id)
                               FROM peachjam_timelineevent
                               WHERE email_alert_sent_at IS NULL
                               GROUP BY user_following_id, event_type);
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
