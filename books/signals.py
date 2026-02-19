from django.db.models.signals import post_save
from django.dispatch import receiver
from books.models import UserBook
from chat.services import AIService
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=UserBook)
def embed_user_book(sender, instance, created, **kwargs):
    logger.info(f"Signal received for UserBook {instance.id}. Created: {created}")
    print(f"Signal received for UserBook {instance.id}. Created: {created}")
    # Skip if status is empty on an update to save API costs
    if not created and not instance.status:
        logger.info("Update skipped due to empty status")
        print("Update skipped due to empty status")
        return

    try:
        logger.info("Embedding user book...")
        print("Embedding user book...")
        service = AIService(instance.user)
        service.add_user_book_to_vectorstore(instance)
        logger.info("Successfully requested embedding")
        print("Successfully requested embedding")
    except Exception as e:
        # Avoid breaking the save process if AI service fails
        logger.error(f"Error embedding user book: {e}")
