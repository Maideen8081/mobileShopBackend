from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import ChatRequestSerializer
from .services import generate_reply


class ChatReplyView(APIView):
    """Public endpoint powering the storefront AI chat assistant.

    Authentication is skipped so guests (no session / no CSRF token) can chat.
    Replies come from the configured AI provider when available, otherwise from
    a deterministic rule-based engine so the widget always works.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        message = serializer.validated_data['message']
        history = serializer.validated_data.get('history') or []

        reply, source = generate_reply(message, history)

        return Response(
            {'success': True, 'reply': reply, 'source': source},
            status=status.HTTP_200_OK,
        )
