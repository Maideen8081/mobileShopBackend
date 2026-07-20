from decimal import Decimal

from django.db.models import Count, Q

from apps.repairs.constants import STATUS_TRANSITIONS
from apps.repairs.models import RepairTicket, RepairTicketPhoto


class RepairTicketService:

    @staticmethod
    def get_dashboard_counts():
        base = RepairTicket.objects
        return {
            'total_tickets': base.count(),
            'pending': base.filter(status='pending').count(),
            'diagnosing': base.filter(status='diagnosing').count(),
            'waiting_approval': base.filter(status='waiting_approval').count(),
            'in_progress': base.filter(status='in_progress').count(),
            'completed': base.filter(status='completed').count(),
            'delivered': base.filter(status='delivered').count(),
            'cancelled': base.filter(status='cancelled').count(),
        }

    @staticmethod
    def update_status(ticket, new_status):
        current = ticket.status
        allowed = STATUS_TRANSITIONS.get(current, [])
        if new_status not in allowed:
            return False, f'Cannot transition from "{current}" to "{new_status}".'
        ticket.status = new_status
        ticket.save(update_fields=['status'])
        return True, 'Status updated successfully.'

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
