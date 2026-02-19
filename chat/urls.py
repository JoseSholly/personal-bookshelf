from django.urls import path
from .views import ChatAPIView
from django.views.generic import TemplateView

urlpatterns = [
    path("api/chat/", ChatAPIView.as_view(), name="chat_api"),
    path("", TemplateView.as_view(template_name="chat/chat.html"), name="chat"),
]
