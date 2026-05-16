# External Book API Integration — Implementation Roadmap

## Overview

The current catalog is seeded with 50 hardcoded classic books (`seed_books`). This roadmap adds the ability to search any book from the Google Books API (3 million+ titles), import it to the user's shelf, and display cover art — all without changing the core RAG pipeline or embedding infrastructure.

---

## Recommended API: Google Books

| Property | Detail |
|---|---|
| Endpoint | `https://www.googleapis.com/books/v1/volumes?q={query}` |
| Auth | API key optional (1 000 req/day free, higher with key) |
| Key fields | `title`, `authors`, `description`, `categories`, `publishedDate`, `industryIdentifiers` (ISBN-10/13), `imageLinks.thumbnail` |
| Fallback covers | Open Library — `https://covers.openlibrary.org/b/isbn/{isbn}-M.jpg` |

No separate account is required for basic search. Add `GOOGLE_BOOKS_API_KEY` to `.env` to raise the quota ceiling.

---

## Phase 1 — Model Changes

**Migration:** `books/0003_book_isbn_cover_source.py`

Add three fields to `Book`:

```python
isbn          = models.CharField(max_length=13, blank=True, db_index=True)
cover_url     = models.URLField(blank=True)          # external thumbnail, no file upload
source        = models.CharField(
    max_length=20,
    choices=[("catalog", "Catalog"), ("google_books", "Google Books"), ("open_library", "Open Library")],
    default="catalog",
)
```

`isbn` is used as the dedup key on import. `cover_url` stores the thumbnail URL directly (no `ImageField`, no media storage). `source` tracks provenance for debugging and display.

**Dedup fallback:** If ISBN is missing (pre-1970 classics, obscure editions) use `(title, author)` as the `get_or_create` key.

---

## Phase 2 — API Client Service

**New file:** `books/api_client.py`

```python
class GoogleBooksClient:
    BASE = "https://www.googleapis.com/books/v1/volumes"

    def search(self, query: str, max_results: int = 10) -> list[dict]:
        """Returns list of normalized book dicts."""

    def get_by_isbn(self, isbn: str) -> dict | None:
        """Fetch a single volume by ISBN."""
```

Normalization maps `volumeInfo` fields → `Book` fields:

| Google Books field | `Book` field |
|---|---|
| `title` | `title` |
| `authors[0]` | `author` |
| `categories[0]` | `genre` |
| `description` | `description` |
| `publishedDate[:4]` | `publication_year` |
| `industryIdentifiers` | `isbn` (prefer ISBN-13) |
| `imageLinks.thumbnail` | `cover_url` (replace `zoom=0` → `zoom=1`) |

The client handles missing fields gracefully (empty string / `None`), timeouts (5 s), and non-200 responses. Import `GOOGLE_BOOKS_API_KEY` from `os.getenv`; if absent, API key param is omitted and the free tier quota applies.

---

## Phase 3 — Views and URLs

**`books/views.py` — two new views:**

### `ExternalBookSearchView`

```
GET /books/search/external/?q=dune
```

- Calls `GoogleBooksClient.search(q)`.
- Returns HTMX partial `books/partials/external_book_results.html`.
- Requires login (`LoginRequiredMixin`).
- Paginated by `max_results=10`; further pages not needed for the initial search UX.

### `ImportExternalBookView`

```
POST /books/import/
Body: { volume_id: "...", isbn: "...", title: "...", ... }
```

- `get_or_create` `Book` by `isbn` (fallback: `title`+`author`).
- `get_or_create` `UserBook` for the requesting user (default status `want_to_read`).
- Returns HTMX partial confirming success (or an error toast if the book already exists on the shelf).
- The existing `post_save` signal on `UserBook` → `AIService.add_user_book_to_vectorstore()` fires automatically — no changes to the RAG pipeline.

**`books/urls.py` additions:**

```python
path("search/external/", ExternalBookSearchView.as_view(), name="external-book-search"),
path("import/", ImportExternalBookView.as_view(), name="import-external-book"),
```

---

## Phase 4 — Templates

### `templates/books/partials/external_book_results.html`

Search result cards, one per volume:
- Cover thumbnail (`cover_url`) with inline SVG fallback.
- Title (serif, `.book-title`), author, year.
- "Add to Shelf" button — HTMX `POST` to `ImportExternalBookView`, swaps the button to a checkmark on success.
- Results container has `id="external-results"` for HTMX targeting.

### `templates/books/book_list.html` — search mode toggle

Add a segmented control above the search bar:

```
[My Library]  [Discover]
```

- "My Library" — existing HTMX live search (current behaviour).
- "Discover" — targets `#external-results`, `hx-get="/books/search/external/"`, debounced `400 ms`.
- Alpine.js `x-data="{ mode: 'library' }"` toggles which input is visible and which results container is shown.

Alternatively, a dedicated `/books/discover/` page works equally well if the toggle adds too much complexity.

---

## Phase 5 — Cover Image Fallback Chain

Everywhere a book cover is rendered, update the template logic:

```html
{% if book.cover_image %}
    <img src="{{ book.cover_image.url }}" alt="{{ book.title }}">
{% elif book.cover_url %}
    <img src="{{ book.cover_url }}" alt="{{ book.title }}">
{% else %}
    {# inline book SVG #}
{% endif %}
```

Files to update: `book_card.html`, `book_row.html`, `book_detail_modal.html`, `user_bookshelf.html` (grid cards).

No `ImageField`, no `MEDIA_ROOT`, no file uploads required.

---

## Phase 6 — Configuration

### `.env` additions

```env
GOOGLE_BOOKS_API_KEY=your_google_books_api_key
```

The key is optional. Without it the client omits `&key=` and falls back to the anonymous quota.

### `bookshelf/settings/base.py` addition

```python
GOOGLE_BOOKS_API_KEY = os.getenv("GOOGLE_BOOKS_API_KEY", "")
```

### CI (`.github/workflows/ci.yml`)

Add `GOOGLE_BOOKS_API_KEY: ""` to the `env:` block. The client must not make real network calls in tests; mock `GoogleBooksClient` in unit tests using `unittest.mock.patch`.

---

## Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Missing ISBN on classic books | Fall back to `(title, author)` as dedup key |
| Genre naming inconsistency | Normalize at import (`"Fiction" → "fiction"`, strip subcategories) |
| Thumbnail too small (128 px) | Replace `zoom=0` with `zoom=1` in the URL for a larger image |
| Google Books quota (1 000/day free) | Add `GOOGLE_BOOKS_API_KEY`; cache results in `django.cache` keyed by query string |
| Import duplicate detection | `get_or_create` by isbn; show "Already on shelf" toast if `UserBook` exists |
| API down / timeout | 5 s timeout; return empty results with a user-visible error toast |

---

## Implementation Order

```
Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6
  (DB)     (client)  (views)   (templates) (covers)  (config)
```

Each phase is independently mergeable. Start with Phase 1 + 2 (no UI changes) to validate the API client in isolation before wiring templates.

---

## What Does Not Change

- `chat/services.py` — the RAG pipeline queries `BookEmbedding` regardless of `Book.source`.
- `books/signals.py` — the `post_save` signal on `UserBook` triggers embedding automatically for imported books.
- `BookEmbedding` migration — no schema changes needed.
- Admin UI — `cover_url` renders as a text field by default; add a `readonly_fields` image preview in `books/admin.py` if desired.
