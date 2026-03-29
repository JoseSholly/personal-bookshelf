from django.http import JsonResponse, StreamingHttpResponse
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from .services import AIService
import logging

logger = logging.getLogger(__name__)


class ChatAPIView(LoginRequiredMixin, View):
    def post(self, request):
        question = request.POST.get("question")
        if not question:
            return JsonResponse({"error": "No question"}, status=400)

        try:
            ai_service = AIService(request.user)
            answer_text = ai_service.ask(question)
        except Exception as e:
            logger.error(e)
            return JsonResponse({"error": str(e)}, status=500)

        # Use streaming response
        # response = StreamingHttpResponse(
        #     ai_service.stream_ask(question), content_type="text/plain"
        # )
        # return response

        return JsonResponse({"answer": answer_text})
