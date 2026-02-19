import json
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from django.views.generic import ListView, CreateView, TemplateView
from django.views.decorators.http import require_http_methods
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from accounts.forms import EmailSignUpForm
from django.db.models import Avg, Subquery, OuterRef, CharField, Q
from django.urls import reverse_lazy
from .models import Book, UserBook
from .forms import UserBookForm


class HomeView(TemplateView):
    template_name = "home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            user_books = UserBook.objects.filter(user=self.request.user)
            context["stats"] = {
                "total_books": user_books.count(),
                "books_read": user_books.filter(status="read").count(),
                "avg_rating": round(
                    user_books.aggregate(Avg("rating"))["rating__avg"] or 0, 1
                ),
                "streak": 0,  # Placeholder for now
            }
        return context


class SignUpView(CreateView):
    form_class = EmailSignUpForm
    success_url = reverse_lazy("login")
    template_name = "registration/signup.html"


class BookListView(ListView):
    model = Book
    template_name = "books/book_list.html"
    context_object_name = "books"
    paginate_by = 20
    ordering = ["title"]

    def get_queryset(self):
        queryset = super().get_queryset()
        query = self.request.GET.get("q")

        if query:
            queryset = queryset.filter(
                Q(title__icontains=query) | Q(author__icontains=query)
            )

        if self.request.user.is_authenticated:
            user_books = UserBook.objects.filter(
                user=self.request.user, book=OuterRef("pk")
            ).values("status")[:1]

            queryset = queryset.annotate(
                user_status=Subquery(user_books, output_field=CharField())
            )
        return queryset

    def get_template_names(self):
        if self.request.headers.get("HX-Request") and not self.request.GET.get("q"):
            return ["books/partials/book_list_elements.html"]
        return ["books/book_list.html"]


class UserBookshelfView(LoginRequiredMixin, ListView):
    model = UserBook
    template_name = "books/user_bookshelf.html"
    context_object_name = "user_books"

    def get_queryset(self):
        return (
            UserBook.objects.filter(user=self.request.user)
            .select_related("book")
            .order_by("-date_updated")
        )


@login_required
def book_detail_modal(request, pk):
    book = get_object_or_404(Book, pk=pk)
    # Check if user already has this book
    user_book = UserBook.objects.filter(user=request.user, book=book).first()
    context = {"book": book, "user_book": user_book}
    return render(request, "books/partials/book_detail_modal.html", context)


@login_required
def add_to_shelf(request, pk):
    book = get_object_or_404(Book, pk=pk)
    user_book, created = UserBook.objects.get_or_create(
        user=request.user, book=book, defaults={"status": "want_to_read"}
    )

    if request.headers.get("HX-Request"):
        # Allow editing immediately after adding
        form = UserBookForm(instance=user_book)
        context = {"form": form, "book": book, "user_book": user_book}
        return render(request, "books/partials/book_modal.html", context)

    return redirect("user_bookshelf")


@login_required
def edit_user_book(request, pk):
    user_book = get_object_or_404(UserBook, pk=pk, user=request.user)

    if request.method == "POST":
        form = UserBookForm(request.POST, instance=user_book)
        if form.is_valid():
            form.save()
            if request.headers.get("HX-Request"):
                # Return the updated row with OOB swap
                response = render(
                    request,
                    "books/partials/book_row.html",
                    {"item": user_book, "is_oob": True},
                )
                response["HX-Trigger"] = json.dumps(
                    {
                        "toast-message": {
                            "message": "Book updated successfully!",
                            "type": "success",
                        }
                    }
                )
                return response
            return redirect("user_bookshelf")
    else:
        form = UserBookForm(instance=user_book)

    context = {"form": form, "book": user_book.book, "user_book": user_book}
    return render(request, "books/partials/book_modal.html", context)


@login_required
@require_http_methods(["DELETE"])
def remove_user_book(request, pk):
    user_book = get_object_or_404(UserBook, pk=pk, user=request.user)
    user_book.delete()
    return HttpResponse("")
