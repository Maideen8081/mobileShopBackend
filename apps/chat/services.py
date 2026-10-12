import logging
import re

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    'You are the PhoneFix Assistant, the friendly customer-support agent for PhoneFix — '
    'a mobile phone store that also repairs devices and sells certified refurbished phones. '
    'Help customers with repairs, order tracking, delivery, warranty, pricing, refurbished '
    'devices and returns. Reply in 2-4 short, practical sentences with a warm tone. Prices '
    'are in Indian Rupees (₹). If a question is unrelated to PhoneFix, gently steer the '
    'conversation back to how you can help with devices, repairs or orders.'
)

_RULES = (
    (
        r'(hi|hello|hey|namaste|good (morning|afternoon|evening))',
        'Hello! 👋 Welcome to PhoneFix. I can help with repairs, orders, warranty and product '
        'questions. What do you need today?',
    ),
    (
        r'(book|repair|fix|broken|crack|screen|battery|water|charging|hang)',
        'I can help you book a repair 🔧. Open the Book Repair page, choose your device, '
        'describe the issue and pick a slot. Most screen and battery repairs are done the same '
        'day. Want to start a booking?',
    ),
    (
        r'(track|order|delivery|ship|where is|status|dispatch|parcel)',
        'You can track any order from the Orders page — it shows live status, courier details '
        'and the expected delivery date 📦. Share your order ID if you want me to point you to it.',
    ),
    (
        r'(warranty|guarantee|covered|coverage)',
        'Every repair includes a 6-month service warranty, and refurbished devices carry a '
        '12-month PhoneFix warranty 🛡️. Keep your invoice safe — that is your warranty proof.',
    ),
    (
        r'(price|cost|how much|charge|rate|quote|estimate)',
        'Repair pricing depends on the device and part. Screen replacements typically start '
        'around ₹1,499 and battery replacements around ₹999 💰. Open Book Repair and select your '
        'model for an exact quote.',
    ),
    (
        r'(refurb|second hand|second-hand|used|renewed|pre-?owned)',
        'Our certified refurbished devices are fully tested, cleaned and come with original-grade '
        'accessories plus a 12-month warranty. Flagship performance at a fraction of the price ♻️.',
    ),
    (
        r'(return|refund|exchange|cancel)',
        'Unused products can be returned within 7 days of delivery, and refunds reach your '
        'original payment method within 5–7 business days. Would you like the returns help page?',
    ),
    (
        r'(human|agent|call|talk|phone|whatsapp|contact|support|help me)',
        'Of course — our team is available 10 AM to 8 PM. Call or WhatsApp +91 98765 43210, or use '
        'the contact links in the footer. I can also keep helping you right here 🙂.',
    ),
    (
        r'(thank|thanks|great|awesome|perfect|nice)',
        'Happy to help! 😊 Anything else you would like to know about your device or order?',
    ),
)

DEFAULT_REPLY = (
    'Thanks for your message! I can help with repairs, order tracking, warranty, pricing, '
    'refurbished devices and returns. Could you tell me a little more about what you need?'
)


def rule_based_reply(message):
    """Deterministic fallback used when no AI provider is configured or reachable."""
    text = (message or '').lower()
    for pattern, reply in _RULES:
        if re.search(pattern, text):
            return reply
    return DEFAULT_REPLY


def _llm_reply(message, history):
    """Call an OpenAI-compatible chat completions endpoint. Returns None on any failure."""
    api_key = getattr(settings, 'AI_CHAT_API_KEY', '')
    if not api_key:
        return None

    base_url = getattr(settings, 'AI_CHAT_BASE_URL', 'https://api.openai.com/v1').rstrip('/')
    model = getattr(settings, 'AI_CHAT_MODEL', 'gpt-4o-mini')

    messages = [{'role': 'system', 'content': SYSTEM_PROMPT}]
    for turn in (history or [])[-8:]:
        role = turn.get('role')
        content = turn.get('content')
        if role in ('user', 'assistant') and content:
            messages.append({'role': role, 'content': content})
    messages.append({'role': 'user', 'content': message})

    try:
        response = requests.post(
            f'{base_url}/chat/completions',
            headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
            json={'model': model, 'messages': messages, 'temperature': 0.4, 'max_tokens': 320},
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        content = data['choices'][0]['message']['content']
        return content.strip() if content else None
    except Exception:
        logger.exception('AI chat completion failed; falling back to rule-based reply')
        return None


def generate_reply(message, history=None):
    """Return a (reply, source) tuple where source is 'ai' or 'rule'."""
    reply = _llm_reply(message, history)
    if reply:
        return reply, 'ai'
    return rule_based_reply(message), 'rule'
