"""Catalog naming and image rules.

These limits are mirrored in the admin UI (src/utils/catalogValidation.ts) and,
where the database can express them, in model constraints. Change all three
together.
"""
import os
import re

from django.core.exceptions import ValidationError

NAME_MIN_LENGTH = 2
NAME_MAX_LENGTH = 60
MAX_SUB_CATEGORIES_PER_CATEGORY = 5

# Starts with a letter or digit; then letters, digits, spaces and & ' ( ) . , / + -
NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 &'().,/+-]*$")

IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.webp')
CATEGORY_IMAGE_MAX_BYTES = 2 * 1024 * 1024


def clean_catalog_name(value, label):
    """Trim, collapse inner whitespace and check length and characters."""
    name = ' '.join((value or '').split())
    if not name:
        raise ValidationError(f'{label} is required.')
    if len(name) < NAME_MIN_LENGTH:
        raise ValidationError(f'{label} must be at least {NAME_MIN_LENGTH} characters.')
    if len(name) > NAME_MAX_LENGTH:
        raise ValidationError(f'{label} must be at most {NAME_MAX_LENGTH} characters.')
    if not NAME_PATTERN.match(name):
        raise ValidationError(
            f"{label} must start with a letter or number and may only contain "
            "letters, numbers, spaces and & ' ( ) . , / + -"
        )
    return name


def validate_image_file(image, max_bytes):
    ext = os.path.splitext(image.name)[1].lower()
    if ext not in IMAGE_EXTENSIONS:
        raise ValidationError('Unsupported image format. Allowed: JPG, JPEG, PNG, WebP.')
    if image.size > max_bytes:
        raise ValidationError(f'Image too large. Max size: {max_bytes // (1024 * 1024)}MB.')


def validate_category_image(image):
    validate_image_file(image, CATEGORY_IMAGE_MAX_BYTES)
