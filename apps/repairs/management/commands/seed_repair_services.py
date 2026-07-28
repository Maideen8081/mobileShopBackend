from django.core.management.base import BaseCommand

from apps.repairs.constants import REPAIR_SERVICES
from apps.repairs.models import RepairService


class Command(BaseCommand):
    help = 'Seed the database with repair services'

    def handle(self, *args, **options):
        created_count = 0
        updated_count = 0

        for service_data in REPAIR_SERVICES:
            service, created = RepairService.objects.update_or_create(
                slug=service_data['slug'],
                defaults={
                    'name': service_data['name'],
                    'description': service_data['description'],
                    'icon': service_data['icon'],
                    'is_active': True,
                },
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'Created: {service.name}'))
            else:
                updated_count += 1
                self.stdout.write(self.style.WARNING(f'Updated: {service.name}'))

        self.stdout.write(
            self.style.SUCCESS(
                f'\nDone! Created: {created_count}, Updated: {updated_count}'
            )
        )
