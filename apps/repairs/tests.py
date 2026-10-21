"""Customer repair tracking: ownership, messaging, courier hand-off and cancellation."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.repairs.models import RepairNote, RepairStatusHistory, RepairTicket
from apps.repairs.services import RepairTicketService

User = get_user_model()

MY_TICKETS = '/api/v1/repairs/my-tickets/'


def my_ticket_url(pk, action=''):
    return f'{MY_TICKETS}{pk}/{action + "/" if action else ""}'


class CustomerRepairBase(TestCase):
    def setUp(self):
        self.client = APIClient(raise_request_exception=False)
        self.customer = User.objects.create_user(email='cust@example.com', password='Str0ng!Pass')
        self.other = User.objects.create_user(email='other@example.com', password='Str0ng!Pass')
        self.ticket = self.make_ticket(self.customer)
        self.client.force_authenticate(self.customer)

    def make_ticket(self, user, status='pending'):
        ticket = RepairTicket.objects.create(
            user=user,
            customer_name='Joe',
            mobile_number='9876543210',
            email=user.email,
            device_brand='Apple',
            device_model='iPhone 13',
            issue_category='Screen Repair',
            problem_description='Cracked screen',
            status=status,
        )
        RepairTicketService.create_ticket_with_history(ticket, updated_by='Joe')
        return ticket


class MyTicketsListTest(CustomerRepairBase):
    def test_lists_only_own_tickets_with_last_update(self):
        self.make_ticket(self.other)
        response = self.client.get(MY_TICKETS)
        self.assertEqual(response.status_code, 200)
        rows = response.data['data']
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['id'], self.ticket.id)
        self.assertIsNone(row['thumbnail'])
        self.assertEqual(row['last_update']['status'], 'pending')
        self.assertEqual(row['last_update']['status_label'], 'Submitted')
        self.assertIn('courier_tracking_number', row)

    def test_requires_authentication(self):
        self.client.force_authenticate(None)
        self.assertIn(self.client.get(MY_TICKETS).status_code, (401, 403))


class MyTicketNoteTest(CustomerRepairBase):
    def test_customer_can_message_own_ticket(self):
        response = self.client.post(my_ticket_url(self.ticket.id, 'notes'), {'message': ' Any update? '}, format='json')
        self.assertEqual(response.status_code, 201)
        note = RepairNote.objects.get(repair_ticket=self.ticket)
        self.assertEqual(note.message, 'Any update?')
        self.assertFalse(note.is_admin)
        self.assertEqual(len(response.data['data']['notes']), 1)

    def test_customer_cannot_post_as_admin(self):
        self.client.post(my_ticket_url(self.ticket.id, 'notes'), {'message': 'hi', 'is_admin': True}, format='json')
        self.assertFalse(RepairNote.objects.get(repair_ticket=self.ticket).is_admin)

    def test_cannot_message_someone_elses_ticket(self):
        foreign = self.make_ticket(self.other)
        response = self.client.post(my_ticket_url(foreign.id, 'notes'), {'message': 'hi'}, format='json')
        self.assertEqual(response.status_code, 404)
        self.assertFalse(RepairNote.objects.filter(repair_ticket=foreign).exists())

    def test_blank_message_rejected(self):
        response = self.client.post(my_ticket_url(self.ticket.id, 'notes'), {'message': '   '}, format='json')
        self.assertEqual(response.status_code, 400)


class MyTicketCourierTest(CustomerRepairBase):
    def test_courier_saved_once_accepted(self):
        self.ticket.status = 'accepted'
        self.ticket.save()
        response = self.client.post(my_ticket_url(self.ticket.id, 'courier'), {
            'courier_company': 'DTDC',
            'courier_tracking_number': 'D123',
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.courier_company, 'DTDC')
        self.assertEqual(self.ticket.courier_tracking_number, 'D123')
        self.assertIsNotNone(self.ticket.courier_pickup_date)
        # Status is untouched: the shop confirms receipt, not the customer.
        self.assertEqual(self.ticket.status, 'accepted')
        self.assertTrue(RepairStatusHistory.objects.filter(
            repair_ticket=self.ticket, updated_by='Customer', notes__contains='D123',
        ).exists())

    def test_courier_rejected_before_acceptance(self):
        response = self.client.post(my_ticket_url(self.ticket.id, 'courier'), {
            'courier_company': 'DTDC',
            'courier_tracking_number': 'D123',
        }, format='json')
        self.assertEqual(response.status_code, 400)

    def test_courier_requires_tracking_number(self):
        self.ticket.status = 'accepted'
        self.ticket.save()
        response = self.client.post(my_ticket_url(self.ticket.id, 'courier'), {'courier_company': 'DTDC'}, format='json')
        self.assertEqual(response.status_code, 400)


class MyTicketCancelTest(CustomerRepairBase):
    def test_cancel_pending_ticket(self):
        response = self.client.post(my_ticket_url(self.ticket.id, 'cancel'), {'reason': 'Fixed it myself'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, 'cancelled')
        self.assertTrue(RepairStatusHistory.objects.filter(
            repair_ticket=self.ticket, status='cancelled', notes__contains='Fixed it myself',
        ).exists())

    def test_cannot_cancel_once_work_started(self):
        self.ticket.status = 'repair_in_progress'
        self.ticket.save()
        response = self.client.post(my_ticket_url(self.ticket.id, 'cancel'), {}, format='json')
        self.assertEqual(response.status_code, 400)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, 'repair_in_progress')

    def test_cannot_cancel_someone_elses_ticket(self):
        foreign = self.make_ticket(self.other)
        response = self.client.post(my_ticket_url(foreign.id, 'cancel'), {}, format='json')
        self.assertEqual(response.status_code, 404)
        foreign.refresh_from_db()
        self.assertEqual(foreign.status, 'pending')
