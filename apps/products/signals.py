"""Back-in-stock emails: fire when a variant's stock goes from 0 to > 0."""

import logging

from django.conf import settings
from django.core.mail import EmailMessage, get_connection
from django.db import transaction
from django.db.models import Q
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from .models import ProductVariant, StockNotification

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=ProductVariant)
def remember_previous_stock(sender, instance, **kwargs):
    if instance.pk:
        instance._previous_stock = (
            ProductVariant.objects.filter(pk=instance.pk).values_list('stock_quantity', flat=True).first()
        )
    else:
        instance._previous_stock = None


@receiver(post_save, sender=ProductVariant)
def notify_on_restock(sender, instance, created, **kwargs):
    previous = getattr(instance, '_previous_stock', None)
    # A brand-new variant with stock also counts as "available again" for product-level subscribers.
    restocked = instance.stock_quantity > 0 and (previous == 0 or (created and previous is None))
    if restocked and instance.is_active:
        transaction.on_commit(lambda: send_restock_emails(instance))


def send_restock_emails(variant):
    pending = StockNotification.objects.filter(
        Q(variant=variant) | Q(variant__isnull=True),
        product_id=variant.product_id,
        notified_at__isnull=True,
    )
    subs = list(pending)
    if not subs:
        return

    product = variant.product
    url = f'{settings.FRONTEND_URL}/product/{product.pk}'
    label = f'{product.product_name} ({variant.variant_name}, {variant.color})'
    messages = [
        EmailMessage(
            subject=f'Back in stock: {product.product_name}',
            body=(
                'Good news!\n\n'
                f'{label} is back in stock at PhoneFix. Stock is limited, so grab it while you can:\n\n'
                f'{url}\n\n'
                'You asked us to let you know when this item was available. '
                'This is a one-time email; we will not contact you again about it.\n'
                '— PhoneFix team'
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[s.email],
        )
        for s in subs
    ]
    try:
        get_connection(fail_silently=False).send_messages(messages)
    except Exception:  # noqa: BLE001 - keep requests pending so a later restock retries them
        logger.exception('Back-in-stock email delivery failed for variant %s', variant.pk)
        return
    StockNotification.objects.filter(pk__in=[s.pk for s in subs]).update(notified_at=timezone.now())
