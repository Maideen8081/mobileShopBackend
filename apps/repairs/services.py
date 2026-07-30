import logging

from django.db import DatabaseError

from apps.repairs.constants import STATUS_LABELS, STATUS_TRANSITIONS
from apps.repairs.models import RepairStatusHistory, RepairTicket, RepairTicketPhoto


logger = logging.getLogger(__name__)


CUSTOMER_APPROVED_TRANSITIONS = {
    'awaiting_approval': {'approve': 'inspection', 'decline': 'cancelled'},
}


class RepairTicketService:

    @staticmethod
    def customer_approve(ticket, action, notes=''):
        allowed = CUSTOMER_APPROVED_TRANSITIONS.get(ticket.status, {})
        new_status = allowed.get(action)
        if not new_status:
            return False, f'Cannot {action} in current status.'

        ticket.status = new_status
        ticket.save(update_fields=['status'])

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
        ticket.save(update_fields=['status'])

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
