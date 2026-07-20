STATUS_TRANSITIONS = {
    'pending': ['diagnosing', 'cancelled'],
    'diagnosing': ['waiting_approval', 'in_progress', 'cancelled'],
    'waiting_approval': ['in_progress', 'cancelled'],
    'in_progress': ['completed', 'cancelled'],
    'completed': ['delivered'],
    'delivered': [],
    'cancelled': [],
}

FIELD_ALIASES = {
    'customer_mobile': 'mobile_number',
    'customer_alternate_mobile so': 'alternate_number',
    'customer_email': 'email',
    'customer_address': 'address',
    'estimated_days': 'estimated_completion_days',
    'images': 'photos',
    'customer_name': 'customer_name',
    'customer_alternate_number': 'alternate_number',
}
