from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("deals", "0002_deal_list_indexes"),
    ]

    operations = [
        # "Account" / "Contact" filters on the deal list (and the deals
        # shown on an account / contact page).
        migrations.AddIndex(
            model_name="djangodealmodel",
            index=models.Index(
                fields=["company", "is_deleted", "account"],
                name="deals_co_account_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="djangodealmodel",
            index=models.Index(
                fields=["company", "is_deleted", "contact"],
                name="deals_co_contact_idx",
            ),
        ),
    ]
