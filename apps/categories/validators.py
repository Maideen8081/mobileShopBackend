import os

from django.core.exceptions import ValidationError


def validate_category_image(image):
    max_size = 2 * 1024 * 1024

    ext = os.path.splitext(image.name)[1].lower()
    allowed = ['.jpg', '.jpeg', '.png', '.webp']
    if ext not in allowed:
        raise ValidationError(f'Unsupported image format. Allowed: {", ".join(allowed)}')

    if image.size > max_size:
        raise ValidationError(f'Image too large. Max size: 2MB')
