from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("actions", "0019_lesson_publication_workflow")]

    operations = [
        migrations.AlterField(
            model_name="treatment", name="method_used",
            field=models.CharField(blank=True, default="", max_length=20,
                                   choices=[("five_whys", "5 WHY"), ("6m", "6M")]),
        ),
    ]
