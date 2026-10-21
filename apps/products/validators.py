"""Product rules, mirrored in the admin UI (src/utils/catalogValidation.ts) and,
where the database can express them, in model constraints. Change all three together.
"""
import re
from decimal import Decimal

from apps.categories.validators import validate_image_file

PRODUCT_NAME_MIN = 2
PRODUCT_NAME_MAX = 200
BRAND_MIN = 2
BRAND_MAX = 100
MODEL_NUMBER_MAX = 100
MODEL_NUMBER_PATTERN = re.compile(r'^[A-Za-z0-9][A-Za-z0-9 ._/+-]*$')
DESCRIPTION_MAX = 5000

MAX_FEATURES = 20
FEATURE_MAX = 255
MAX_CARE_INSTRUCTIONS = 20
CARE_INSTRUCTION_MAX = 500

MAX_VARIANTS = 20
MAX_IMAGES_PER_VARIANT = 10
IMAGE_MAX_BYTES = 5 * 1024 * 1024

PRICE_MAX = Decimal('99999999.99')
STOCK_MAX = 100000
LOW_STOCK_ALERT_MAX = 1000
BATTERY_MIN = 500
BATTERY_MAX = 20000


def validate_product_image(image):
    validate_image_file(image, IMAGE_MAX_BYTES)
