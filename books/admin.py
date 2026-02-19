from django.contrib import admin
from .models import Book, UserBook


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
    autocomplete_fields = (
        "book",
    )  # user might be fine as select, but book list can grow
