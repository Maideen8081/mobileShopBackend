from apps.repairs.constants import STATUS_LABELS, STATUS_TRANSITIONS
from apps.repairs.models import RepairStatusHistory, RepairTicket, RepairTicketPhoto


class RepairTicketService:

    @staticmethod
    def get_dashboard_counts():
        base = RepairTicket.objects
        return {
            'total_tickets': base.count(),
            'online_tickets': base.filter(source='online').count(),
            'local_tickets': base.filter(source='local').count(),
            'pending': base.filter(status='pending').count(),
            'device_received': base.filter(status='device_received').count(),
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
    def update_status(ticket, new_status, updated_by='Admin', notes=''):
        current = ticket.status
        allowed = STATUS_TRANSITIONS.get(current, [])
        if new_status not in allowed:
            return False, f'Cannot transition from "{STATUS_LABELS.get(current, current)}" to "{STATUS_LABELS.get(new_status, new_status)}".'

        ticket.status = new_status
        ticket.save(update_fields=['status'])

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
