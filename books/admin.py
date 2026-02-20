from django.contrib import admin
from .models import Book, UserBook, BookEmbedding


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "genre", "publication_year")
    search_fields = ("title", "author", "genre")
    list_filter = ("genre", "publication_year")


@admin.register(UserBook)
class UserBookAdmin(admin.ModelAdmin):
    list_display = ("user", "book", "status", "rating", "date_updated")
    list_filter = ("status", "rating", "date_updated")
    search_fields = ("user__username", "book__title", "book__author")
    autocomplete_fields = ("book",)


@admin.register(BookEmbedding)
class BookEmbeddingAdmin(admin.ModelAdmin):
    list_display = ("user", "user_book", "updated_at", "content_preview")
    list_filter = ("updated_at",)
    search_fields = (
        "user__username",
        "user__email",
        "user_book__book__title",
        "user_book__book__author",
    )
    readonly_fields = (
        "user",
        "user_book",
        "content",
        "embedding_preview",
        "updated_at",
    )
    exclude = ("embedding",)  # hide the raw vector — too large to display usefully

    # ── Custom columns ────────────────────────────────────────────────────────

    @admin.display(description="Content preview")
    def content_preview(self, obj):
        return obj.content[:120] + "…" if len(obj.content) > 120 else obj.content

    @admin.display(description="Embedding (first 8 dims)")
    def embedding_preview(self, obj):
        if obj.embedding is not None:
            preview = [round(v, 4) for v in obj.embedding[:8]]
            return f"{preview}  … ({len(obj.embedding)} dims)"
        return "—"

    # ── Fieldsets for the detail view ─────────────────────────────────────────

    fieldsets = (
        (
            "Ownership",
            {
                "fields": ("user", "user_book"),
            },
        ),
        (
            "Embedded content",
            {
                "fields": ("content", "embedding_preview", "updated_at"),
            },
        ),
    )
