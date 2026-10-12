from django.urls import path

from .views import ChatReplyView

app_name = 'chat'

urlpatterns = [
    path('', ChatReplyView.as_view(), name='reply'),
]
