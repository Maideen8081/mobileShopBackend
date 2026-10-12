"""AI chat endpoint: public access, validation, and rule-based fallback."""

from unittest import mock

from django.test import TestCase
from rest_framework.test import APIClient

from apps.chat.services import rule_based_reply

CHAT_URL = '/api/v1/chat/'


class ChatReplyViewTest(TestCase):
    def setUp(self):
        self.client = APIClient(raise_request_exception=False)

    def test_guest_can_get_a_reply(self):
        response = self.client.post(CHAT_URL, {'message': 'Hello there'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])
        self.assertIn('reply', response.data)
        self.assertTrue(response.data['reply'])

    def test_falls_back_to_rules_without_api_key(self):
        response = self.client.post(CHAT_URL, {'message': 'I need to book a screen repair'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['source'], 'rule')

    def test_missing_message_is_rejected(self):
        response = self.client.post(CHAT_URL, {}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_history_is_accepted(self):
        payload = {
            'message': 'and the warranty?',
            'history': [
                {'role': 'user', 'content': 'I bought a refurbished phone'},
                {'role': 'assistant', 'content': 'Great choice!'},
            ],
        }
        response = self.client.post(CHAT_URL, payload, format='json')
        self.assertEqual(response.status_code, 200)

    def test_llm_reply_is_used_when_configured(self):
        with mock.patch('apps.chat.services._llm_reply', return_value='AI generated answer'):
            response = self.client.post(CHAT_URL, {'message': 'anything'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['reply'], 'AI generated answer')
        self.assertEqual(response.data['source'], 'ai')


class ChatRulesTest(TestCase):
    def test_repair_keyword_matches(self):
        self.assertIn('repair', rule_based_reply('my screen is cracked').lower())

    def test_unknown_falls_back_to_default(self):
        self.assertTrue(rule_based_reply('xyzzy nonsense query').strip())
