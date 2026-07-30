STATUS_TRANSITIONS = {
    'pending': ['accepted', 'rejected', 'cancelled'],
    'accepted': ['device_received', 'cancelled'],
    'rejected': [],
    'device_received': ['awaiting_approval', 'cancelled'],
    'awaiting_approval': ['inspection', 'cancelled'],
    'inspection': ['waiting_parts', 'repair_in_progress', 'cancelled'],
    'waiting_parts': ['repair_in_progress', 'cancelled'],
    'repair_in_progress': ['quality_check', 'cancelled'],
    'quality_check': ['ready_for_pickup', 'repair_in_progress', 'cancelled'],
    'ready_for_pickup': ['shipped', 'completed', 'cancelled'],
    'shipped': ['completed', 'cancelled'],
    'completed': [],
    'cancelled': [],
}

STATUS_LABELS = {
    'pending': 'Submitted',
    'accepted': 'Accepted',
    'rejected': 'Rejected',
    'device_received': 'Received',
    'awaiting_approval': 'Awaiting Approval',
    'inspection': 'Diagnosing',
    'waiting_parts': 'Waiting for Parts',
    'repair_in_progress': 'Repair In Progress',
    'quality_check': 'Quality Check',
    'ready_for_pickup': 'Ready for Delivery',
    'shipped': 'Shipped',
    'completed': 'Completed',
    'cancelled': 'Cancelled',
}

FIELD_ALIASES = {
    'customer_mobile': 'mobile_number',
    'customer_alternate_mobile': 'alternate_number',
    'customer_alternate_number': 'alternate_number',
    'customer_email': 'email',
    'customer_address': 'address',
    'images': 'photos',
    'estimated_days': 'estimated_completion_days',
    'device_category': 'issue_category',
}

REPAIR_SERVICES = [
    {
        'name': 'Screen Repair',
        'slug': 'screen-repair',
        'description': 'Cracked or shattered screen? We replace it with premium OEM-grade glass in under 60 minutes.',
        'icon': 'screen_lock_portrait',
    },
    {
        'name': 'Battery Replacement',
        'slug': 'battery-replacement',
        'description': 'Fast, reliable battery swaps to bring your device back to full life with genuine components.',
        'icon': 'battery_charging_full',
    },
    {
        'name': 'Water Damage Repair',
        'slug': 'water-damage-repair',
        'description': 'Advanced ultrasonic cleaning and component-level restoration for liquid-damaged devices.',
        'icon': 'water_damage',
    },
    {
        'name': 'Camera Repair',
        'slug': 'camera-repair',
        'description': 'Fixing blurry shots, broken lenses, and camera module failures on all major brands.',
        'icon': 'camera_alt',
    },
    {
        'name': 'Charging Port Fix',
        'slug': 'charging-port-fix',
        'description': 'Loose or non-functional charging port? We diagnose and repair or replace the port assembly.',
        'icon': 'charging_station',
    },
    {
        'name': 'Speaker & Mic Repair',
        'slug': 'speaker-mic-repair',
        'description': 'Restore sound quality with precise speaker, earpiece, and microphone repairs.',
        'icon': 'volume_up',
    },
    {
        'name': 'Software Unlocking',
        'slug': 'software-unlocking',
        'description': 'iCloud lock removal, FRP bypass, and software-level issues resolved securely.',
        'icon': 'lock',
    },
    {
        'name': 'Motherboard Repair',
        'slug': 'motherboard-repair',
        'description': 'Advanced micro-soldering for board-level issues including no power, water damage, and more.',
        'icon': 'memory',
    },
]
