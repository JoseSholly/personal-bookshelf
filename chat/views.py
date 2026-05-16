from django.http import JsonResponse, StreamingHttpResponse
from django.views import View
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from .services import AIService
import logging

logger = logging.getLogger(__name__)


class ChatView(LoginRequiredMixin, TemplateView):
    template_name = "chat/chat.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from books.models import UserBook

        user_books = UserBook.objects.filter(user=self.request.user)
        reading = (
            user_books.filter(status="reading")
            .select_related("book")
            .order_by("-date_updated")
            .first()
        )
        context["chat_stats"] = {
            "total": user_books.count(),
            "reading": user_books.filter(status="reading").count(),
            "want_to_read": user_books.filter(status="want_to_read").count(),
            "read": user_books.filter(status="read").count(),
            "current_book": reading.book.title if reading else None,
        }
        return context


class ChatAPIView(LoginRequiredMixin, View):
    def post(self, request):
        question = request.POST.get("question")
        if not question:
            return JsonResponse({"error": "No question"}, status=400)

        ai_service = AIService(request.user)

        def token_stream():
            try:
                for token in ai_service.stream_ask(question):
                    if token:
                        yield token
            except Exception as e:
                # Headers are already sent at this point, so the error has to
                # be delivered in-band as part of the streamed body.
                logger.error("Streaming failed: %s", e, exc_info=True)
                yield "\n\nSorry, I couldn't complete that response."

        response = StreamingHttpResponse(
            token_stream(), content_type="text/plain; charset=utf-8"
        )
        # Defeat proxy/server buffering so tokens reach the client immediately.
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response
