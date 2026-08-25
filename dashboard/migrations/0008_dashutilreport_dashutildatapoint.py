from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0007_kpireport_kpidatapoint'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='DashUtilReport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('file', models.FileField(upload_to='dash_util/')),
                ('period_type', models.CharField(choices=[('weekly','Weekly'),('monthly','Monthly')], max_length=10)),
                ('period_label', models.CharField(max_length=50)),
                ('year', models.IntegerField()),
                ('month', models.IntegerField(blank=True, null=True)),
                ('week', models.IntegerField(blank=True, null=True)),
                ('week_start_date', models.DateField(blank=True, null=True)),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('uploaded_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-year', '-month', '-week']},
        ),
        migrations.CreateModel(
            name='DashUtilDataPoint',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('county', models.CharField(blank=True, db_index=True, max_length=100)),
                ('sub_county', models.CharField(blank=True, db_index=True, max_length=100)),
                ('active_users', models.IntegerField(blank=True, null=True)),
                ('total_users', models.IntegerField(blank=True, null=True)),
                ('utilization_pct', models.FloatField(blank=True, null=True)),
                ('report', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='data_points', to='dashboard.dashutilreport')),
            ],
            options={'unique_together': {('report', 'county', 'sub_county')}},
        ),
    ]