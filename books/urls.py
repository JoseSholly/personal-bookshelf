from django.urls import path
from . import views

urlpatterns = [
    path("", views.BookListView.as_view(), name="book_list"),
    path("signup/", views.SignUpView.as_view(), name="signup"),
    path("my-books/", views.UserBookshelfView.as_view(), name="user_bookshelf"),
    path("books/<int:pk>/modal/", views.book_detail_modal, name="book_detail_modal"),
    path("books/<int:pk>/add/", views.add_to_shelf, name="add_to_shelf"),
    path("my-books/<int:pk>/edit/", views.edit_user_book, name="edit_user_book"),
    path("my-books/<int:pk>/remove/", views.remove_user_book, name="remove_user_book"),
]
