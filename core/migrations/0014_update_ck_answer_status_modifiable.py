from django.db import migrations

SQL_DROP = """
ALTER TABLE core_answer
DROP CONSTRAINT IF EXISTS ck_answer_status_modifiable;
"""


SQL_ADD = """
ALTER TABLE core_answer
ADD CONSTRAINT ck_answer_status_modifiable
CHECK (
  (status = 'pending' AND modifiable = TRUE)
  OR (status IN ('waiting', 'waiting_for_approval', 'approved', 'rejected') AND modifiable = FALSE)
);
"""

class Migration(migrations.Migration):

    dependencies = [
        ("core", "0013_parameterchangelog"), 
    ]

    operations = [
        migrations.RunSQL(SQL_DROP, reverse_sql=""),
        migrations.RunSQL(SQL_ADD, reverse_sql=SQL_DROP),
    ]
