"""Server-side validation of the admin repair-ticket forms and status updates."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.repairs.models import RepairTicket
from apps.repairs.services import RepairTicketService

User = get_user_model()

VALID = {
    'customer_name': 'Ravi Kumar',
    'mobile_number': '98765-43210',
    'device_brand': 'Samsung',
    'device_model': 'Galaxy S23',
    'imei_number': '35 209 900 176148 1',
    'issue_category': 'Screen Repair',
    'problem_description': 'Display flickers and has a crack at the top.',
    'estimated_cost': '4500',
    'estimated_completion_days': '3',
}


class AdminRepairValidationTest(TestCase):
    def setUp(self):
        self.client = APIClient(raise_request_exception=False)
        admin = User.objects.create_user(email='admin@example.com', password='Str0ng!Pass', role='admin', is_staff=True)
        self.client.force_authenticate(admin)

    def create(self, **overrides):
        return self.client.post('/api/v1/repairs/create/', {**VALID, **overrides}, format='multipart')

    def test_valid_ticket_normalises_numbers(self):
        r = self.create()
        self.assertIn(r.status_code, (200, 201), r.data)
        ticket = RepairTicket.objects.get()
        self.assertEqual(ticket.mobile_number, '9876543210')
        self.assertEqual(ticket.imei_number, '352099001761481')

    def test_bad_imei_is_rejected_not_dropped(self):
        r = self.create(imei_number='12345')
        self.assertEqual(r.status_code, 400)
        self.assertFalse(RepairTicket.objects.exists())

    def test_field_rules(self):
        cases = {
            'customer_name': 'R2D2',
            'problem_description': 'broken',
            'estimated_cost': '-1',
            'estimated_completion_days': '0',
            'alternate_number': '9876543210',  # same as mobile
        }
        for field, value in cases.items():
            with self.subTest(field=field):
                self.assertEqual(self.create(**{field: value}).status_code, 400)

    def test_status_update_rules(self):
        ticket = RepairTicket.objects.create(
            customer_name='Ravi', mobile_number='9876543210', device_brand='Samsung',
            device_model='S23', issue_category='Screen', problem_description='Cracked glass',
        )
        RepairTicketService.create_ticket_with_history(ticket)
        url = f'/api/v1/repairs/{ticket.pk}/status/'
        self.assertEqual(self.client.put(url, {'status': 'teleported'}, format='json').status_code, 400)
        self.assertEqual(self.client.put(url, {'status': 'rejected'}, format='json').status_code, 400)
        self.assertEqual(self.client.put(url, {'status': 'accepted', 'repair_charge': '-10'}, format='json').status_code, 400)
        r = self.client.put(url, {'status': 'rejected', 'notes': 'Water damage, not repairable'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
