import logging

from django.db import DatabaseError

from apps.repairs.constants import STATUS_LABELS, STATUS_TRANSITIONS
from apps.repairs.models import RepairStatusHistory, RepairTicket, RepairTicketPhoto


logger = logging.getLogger(__name__)


CUSTOMER_APPROVED_TRANSITIONS = {
    'awaiting_approval': {'approve': 'inspection', 'decline': 'cancelled'},
}

# A customer may only withdraw a request before the device is with the shop.
CUSTOMER_CANCELLABLE_STATUSES = ('pending', 'accepted')


class RepairTicketService:

    @staticmethod
    def customer_cancel(ticket, reason=''):
        if ticket.status not in CUSTOMER_CANCELLABLE_STATUSES:
            return False, 'This repair can no longer be cancelled online. Please contact support.'
        notes = f'Cancelled by customer. Reason: {reason}' if reason else 'Cancelled by customer.'
        return RepairTicketService.update_status(ticket, 'cancelled', updated_by='Customer', notes=notes)

    @staticmethod
    def customer_submit_courier(ticket, courier_company, tracking_number, pickup_date=None, notes=''):
        if ticket.status != 'accepted':
            return False, 'Courier details can only be added once the repair is accepted and before the device is received.'

        ticket.courier_company = courier_company
        ticket.courier_tracking_number = tracking_number
        ticket.courier_pickup_date = pickup_date
        ticket.save(update_fields=['courier_company', 'courier_tracking_number', 'courier_pickup_date', 'updated_at'])

        history_notes = f'Customer shipped the device via {courier_company} (tracking {tracking_number}).'
        if notes:
            history_notes = f'{history_notes} {notes}'
        RepairStatusHistory.objects.create(
            repair_ticket=ticket,
            status=ticket.status,
            updated_by='Customer',
            notes=history_notes,
        )
        return True, 'Courier details saved.'

    @staticmethod
    def customer_approve(ticket, action, notes=''):
        allowed = CUSTOMER_APPROVED_TRANSITIONS.get(ticket.status, {})
        new_status = allowed.get(action)
        if not new_status:
            return False, f'Cannot {action} in current status.'

        ticket.status = new_status
        ticket.save(update_fields=['status', 'updated_at'])

        if action == 'approve':
            ticket.customer_approved = True
            try:
                ticket.save(update_fields=['customer_approved'])
            except DatabaseError:
                logger.exception('Failed to save customer_approved (column may not exist yet)')

        label = 'approved' if action == 'approve' else 'declined'
        RepairStatusHistory.objects.create(
            repair_ticket=ticket,
            status=new_status,
            updated_by='Customer',
            notes=notes or f'Customer {label} the repair estimate.',
        )

        return True, f'Customer {label} the repair estimate.'

    @staticmethod
    def get_dashboard_counts():
        base = RepairTicket.objects
        return {
            'total_tickets': base.count(),
            'online_tickets': base.filter(source='online').count(),
            'local_tickets': base.filter(source='local').count(),
            'pending': base.filter(status='pending').count(),
            'accepted': base.filter(status='accepted').count(),
            'rejected': base.filter(status='rejected').count(),
            'device_received': base.filter(status='device_received').count(),
            'awaiting_approval': base.filter(status='awaiting_approval').count(),
            'inspection': base.filter(status='inspection').count(),
            'waiting_parts': base.filter(status='waiting_parts').count(),
            'repair_in_progress': base.filter(status='repair_in_progress').count(),
            'quality_check': base.filter(status='quality_check').count(),
            'ready_for_pickup': base.filter(status='ready_for_pickup').count(),
            'shipped': base.filter(status='shipped').count(),
            'completed': base.filter(status='completed').count(),
            'cancelled': base.filter(status='cancelled').count(),
        }

    @staticmethod
    def update_status(ticket, new_status, updated_by='Admin', notes='', extra_fields=None):
        current = ticket.status
        allowed = STATUS_TRANSITIONS.get(current, [])
        if new_status not in allowed:
            return False, f'Cannot transition from "{STATUS_LABELS.get(current, current)}" to "{STATUS_LABELS.get(new_status, new_status)}".'

        ticket.status = new_status
        ticket.save(update_fields=['status', 'updated_at'])

        if extra_fields:
            for field, value in extra_fields.items():
                setattr(ticket, field, value)
            try:
                ticket.save(update_fields=list(extra_fields.keys()))
            except DatabaseError:
                logger.exception('Failed to save extra fields (columns may not exist yet)')

        RepairStatusHistory.objects.create(
            repair_ticket=ticket,
            status=new_status,
            updated_by=updated_by,
            notes=notes,
        )

        return True, f'Status updated to "{STATUS_LABELS.get(new_status, new_status)}".'

    @staticmethod
    def create_ticket_with_history(ticket, updated_by='System'):
        RepairStatusHistory.objects.create(
            repair_ticket=ticket,
            status=ticket.status,
            updated_by=updated_by,
            notes='Ticket created.',
        )

    @staticmethod
    def assign_technician(ticket, technician_name):
        ticket.assigned_technician = technician_name
        ticket.save(update_fields=['assigned_technician'])
        return True, 'Technician assigned successfully.'

    @staticmethod
    def create_photos(ticket, images):
        created = []
        for image in images:
            photo = RepairTicketPhoto.objects.create(
                repair_ticket=ticket,
                image=image,
            )
            created.append(photo)
        return created
