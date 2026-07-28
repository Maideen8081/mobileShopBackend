import logging
from datetime import datetime

from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string

from apps.repairs.constants import STATUS_LABELS
from apps.repairs.models import Notification, RepairTicket

logger = logging.getLogger(__name__)


def _send_email(to_email, subject, body):
    try:
        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@mobileshop.com'),
            to=[to_email],
        )
        email.send(fail_silently=True)
        logger.info('[notification] Email sent to %s: %s', to_email, subject)
        return True
    except Exception as e:
        logger.error('[notification] Failed to send email to %s: %s', to_email, e)
        return False


def _send_sms(phone_number, message):
    # SMS stub — integrate with Twilio, MSG91, etc.
    logger.info('[notification] SMS to %s: %s', phone_number, message)
    return True


def _create_notification(user, ticket, title, message, notification_type='email'):
    notification = Notification.objects.create(
        user=user,
        repair_ticket=ticket,
        title=title,
        message=message,
        notification_type=notification_type,
        sent_at=datetime.now(),
    )
    return notification


def send_ticket_created_notification(ticket):
    subject = f'Repair Ticket Created - {ticket.ticket_number}'
    body = (
        f'Hello {ticket.customer_name},\n\n'
        f'Your repair ticket has been created successfully.\n\n'
        f'Ticket Number: {ticket.ticket_number}\n'
        f'Service: {ticket.issue_category}\n'
        f'Device: {ticket.device_brand} {ticket.device_model}\n'
        f'Status: {STATUS_LABELS.get(ticket.status, ticket.status)}\n\n'
        f'You can track your repair status using the app.\n\n'
        f'Thank you!'
    )

    if ticket.email:
        _send_email(ticket.email, subject, body)

    if ticket.mobile_number:
        sms_msg = f'Your repair ticket {ticket.ticket_number} has been created. Status: {STATUS_LABELS.get(ticket.status, "Pending")}. Track in the app.'
        _send_sms(ticket.mobile_number, sms_msg)

    if ticket.user:
        _create_notification(ticket.user, ticket, subject, body)


def send_status_update_notification(ticket, old_status, new_status):
    status_label = STATUS_LABELS.get(new_status, new_status)
    subject = f'Repair Status Update - {ticket.ticket_number}'
    body = (
        f'Hello {ticket.customer_name},\n\n'
        f'Your repair ticket status has been updated.\n\n'
        f'Ticket Number: {ticket.ticket_number}\n'
        f'Device: {ticket.device_brand} {ticket.device_model}\n'
        f'Previous Status: {STATUS_LABELS.get(old_status, old_status)}\n'
        f'Current Status: {status_label}\n\n'
    )

    if new_status == 'ready_for_pickup':
        body += 'Your device is ready for pickup!\n\n'
    elif new_status == 'completed':
        body += 'Your repair has been completed. Thank you!\n\n'
    elif new_status == 'cancelled':
        body += 'Your repair ticket has been cancelled.\n\n'
    else:
        body += 'You can track your repair status using the app.\n\n'

    body += 'Thank you!'

    if ticket.email:
        _send_email(ticket.email, subject, body)

    if ticket.mobile_number:
        sms_msg = f'Your repair ticket {ticket.ticket_number} status updated to: {status_label}.'
        _send_sms(ticket.mobile_number, sms_msg)

    if ticket.user:
        _create_notification(ticket.user, ticket, subject, body)


def send_ticket_assigned_notification(ticket, technician_name):
    subject = f'Technician Assigned - {ticket.ticket_number}'
    body = (
        f'Hello {ticket.customer_name},\n\n'
        f'A technician has been assigned to your repair ticket.\n\n'
        f'Ticket Number: {ticket.ticket_number}\n'
        f'Technician: {technician_name}\n'
        f'Device: {ticket.device_brand} {ticket.device_model}\n\n'
        f'Thank you!'
    )

    if ticket.email:
        _send_email(ticket.email, subject, body)

    if ticket.user:
        _create_notification(ticket.user, ticket, subject, body)
