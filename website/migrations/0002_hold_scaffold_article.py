from django.db import migrations


def hold_scaffold_article(apps, schema_editor):
    Post = apps.get_model("website", "Post")
    Post.objects.filter(title="Why Premium Cleaning Wins in Urban Properties", body__contains="That is where SG AllClean is positioned: premium, recurring, and detail-led.").update(status="draft")


class Migration(migrations.Migration):
    dependencies = [("website", "0001_initial")]
    operations = [migrations.RunPython(hold_scaffold_article, migrations.RunPython.noop)]
