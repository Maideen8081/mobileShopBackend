from datetime import datetime

from django.db.models import Max


def generate_ticket_number():
    from .models import RepairTicket
    year = datetime.now().year
    prefix = f'RPR-{year}-'
    max_ticket = RepairTicket.objects.filter(
        ticket_number__startswith=prefix
    ).aggregate(Max('ticket_number'))['ticket_number__max']

    if max_ticket:
        last_num = int(max_ticket.split('-')[-1])
        new_num = last_num + 1
    else:
        new_num = 1

    return f'{prefix}{new_num:04d}'
