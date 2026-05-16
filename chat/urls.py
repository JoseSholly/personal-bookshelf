from django.urls import path
from .views import ChatAPIView, ChatView

urlpatterns = [
    path("api/chat/", ChatAPIView.as_view(), name="chat_api"),
    path("", ChatView.as_view(), name="chat"),
]
