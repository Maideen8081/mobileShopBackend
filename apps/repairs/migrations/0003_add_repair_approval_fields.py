from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('repairs', '0002_rebuild_repair_schema'),
    ]

    operations = [
        migrations.AddField(
            model_name='repairticket',
            name='repair_reason',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='repairticket',
            name='repair_charge',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='repairticket',
            name='customer_approved',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='repairticket',
            name='status',
            field=models.CharField(choices=[
                ('pending', 'Pending'),
                ('accepted', 'Accepted'),
                ('rejected', 'Rejected'),
                ('device_received', 'Device Received'),
                ('awaiting_approval', 'Awaiting Approval'),
                ('inspection', 'Inspection'),
                ('waiting_parts', 'Waiting for Parts'),
                ('repair_in_progress', 'Repair In Progress'),
                ('quality_check', 'Quality Check'),
                ('ready_for_pickup', 'Ready for Pickup'),
                ('shipped', 'Shipped'),
                ('completed', 'Completed'),
                ('cancelled', 'Cancelled'),
            ], default='pending', max_length=30),
        ),
    ]
