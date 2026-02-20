from django.db import models
from django.contrib.auth.models import User
from pgvector.django import VectorField
import os


class Book(models.Model):
    title = models.CharField(max_length=255)
    author = models.CharField(max_length=255)
    genre = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    publication_year = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.title} by {self.author}"


class UserBook(models.Model):
    STATUS_CHOICES = [
        ("want_to_read", "Want to Read"),
        ("reading", "Reading"),
        ("read", "Read"),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="want_to_read"
    )
    rating = models.PositiveSmallIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)
    date_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "book")

    def __str__(self):
        return f"{self.user} - {self.book.title} ({self.status})"


class BookEmbedding(models.Model):
    """Stores pgvector embeddings for a user's books.

    One row per UserBook — upserted whenever the UserBook changes.
    The vector dimension (768) matches gemini-embedding-001 output.
    """

    user_book = models.OneToOneField(
        UserBook,
        on_delete=models.CASCADE,
        related_name="embedding",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="book_embeddings",
    )
    content = models.TextField(help_text="The plain-text that was embedded.")
    embedding = VectorField(dimensions=os.getenv("EMBEDDING_DIMENSIONS", 768))
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = []  # IVFFlat / HNSW index added in migration for production

    def __str__(self):
        return f"Embedding: {self.user_book}"
