"""Field validators shared by admin-facing serializers.

Each returns the cleaned value or raises ``serializers.ValidationError`` with a
message written for the person filling in the form.
"""

import re
from decimal import Decimal

from rest_framework import serializers

NAME_RE = re.compile(r"^[A-Za-z][A-Za-z .'\-]*$")
INDIAN_MOBILE_RE = re.compile(r'^[6-9]\d{9}$')
MONEY_MAX = Decimal('9999999.99')


def clean_person_name(value, label='Name', min_len=2, max_len=100):
    value = ' '.join(str(value or '').split())
    if not value:
        raise serializers.ValidationError(f'{label} is required.')
    if len(value) < min_len:
        raise serializers.ValidationError(f'{label} must be at least {min_len} characters.')
    if len(value) > max_len:
        raise serializers.ValidationError(f'{label} must be at most {max_len} characters.')
    if not NAME_RE.match(value):
        raise serializers.ValidationError(f'{label} can only contain letters, spaces, dots, apostrophes and hyphens.')
    return value


def clean_indian_mobile(value, label='Mobile number', required=True):
    digits = re.sub(r'\D', '', str(value or ''))
    if len(digits) == 12 and digits.startswith('91'):
        digits = digits[2:]
    if not digits:
        if required:
            raise serializers.ValidationError(f'{label} is required.')
        return ''
    if not INDIAN_MOBILE_RE.match(digits):
        raise serializers.ValidationError(f'{label} must be a valid 10-digit Indian number starting with 6-9.')
    return digits


def clean_required_text(value, label, min_len=1, max_len=None):
    value = ' '.join(str(value or '').split())
    if not value:
        raise serializers.ValidationError(f'{label} is required.')
    if len(value) < min_len:
        raise serializers.ValidationError(f'{label} must be at least {min_len} characters.')
    if max_len and len(value) > max_len:
        raise serializers.ValidationError(f'{label} must be at most {max_len} characters.')
    return value


def clean_amount(value, label='Amount', allow_zero=False):
    if value is None:
        raise serializers.ValidationError(f'{label} is required.')
    if value < 0 or (value == 0 and not allow_zero):
        raise serializers.ValidationError(f'{label} must be greater than zero.')
    if value > MONEY_MAX:
        raise serializers.ValidationError(f'{label} is too large.')
    return value
