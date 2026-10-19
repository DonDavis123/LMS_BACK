from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("leads", "0007_leads_dashboard_idx"),
    ]

    operations = [
        migrations.AlterField(
            model_name="djangoleadmodel",
            name="lead_source",
            field=models.CharField(
                choices=[('None', 'None'), ('Advertisement', 'Advertisement'), ('Cold Call', 'Cold Call'), ('Employee Referral', 'Employee Referral'), ('External Referral', 'External Referral'), ('Online Store', 'Online Store'), ('Partner', 'Partner'), ('Public Relations', 'Public Relations'), ('Sales Email Alias', 'Sales Email Alias'), ('Seminar Partner', 'Seminar Partner'), ('Internal Seminar', 'Internal Seminar'), ('Trade Show', 'Trade Show'), ('Web Download', 'Web Download'), ('Web Research', 'Web Research'), ('Chat', 'Chat'), ('X (Twitter)', 'X (Twitter)'), ('Facebook', 'Facebook'), ('Other', 'Other')],
                default="None",
                max_length=100,
            ),
        ),
    ]
