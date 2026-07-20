import os
import re

from django.core.exceptions import ValidationError


def validate_mobile_number(value):
    if not re.match(r'^\d{10,15}$', value):
        raise ValidationError('Mobile number must contain only digits and be 10-15 characters long.')


def validate_imei_number(value):
    if value and not re.match(r'^\d{15}$', value):
        raise ValidationError('IMEI number must be exactly 15 digits.')


def validate_estimated_cost(value):
    if value < 0:
        raise ValidationError('Estimated cost cannot be negative.')


def validate_completion_days(value):
    if value < 1:
        raise ValidationError('Estimated completion days must be at least 1.')


def validate_repair_image(image):
    max_size = 5 * 1024 * 1024
    ext = os.path.splitext(image.name)[1].lower()
    allowed = ['.jpg', '.jpeg', '.png', '.webp']
    if ext not in allowed:
        raise ValidationError(f'Unsupported image format. Allowed: {", ".join(allowed)}')
    if image.size > max_size:
        raise ValidationError(f'Image too large. Max size: 5MB')
