from django.db import migrations


NEW_TEXT = "Experience in property management and Airbnb hosting shapes the service."
OLD_PREFIX = "SG AllClean is led by "
OLD_SENTENCE_END = "property management and Airbnb hosting experience shapes the service."


def remove_person_name(apps, schema_editor):
    Page = apps.get_model("website", "Page")
    pages = Page.objects.filter(
        slug="about",
        body__startswith=OLD_PREFIX,
        body__contains=OLD_SENTENCE_END,
    )
    for page in pages:
        remainder = page.body.partition(OLD_SENTENCE_END)[2]
        page.body = NEW_TEXT + remainder
        page.save(update_fields=["body"])


class Migration(migrations.Migration):
    dependencies = [
        ("website", "0003_adminloginthrottle_alter_navitem_path_and_more"),
    ]

    operations = [
        migrations.RunPython(remove_person_name, migrations.RunPython.noop),
    ]
