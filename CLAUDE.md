# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Start dev server
python manage.py runserver

# Seed the book catalog (50 classic books)
python manage.py seed_books

# Create admin user
python manage.py createsuperuser
```

## Environment Variables

Create a `.env` file in the project root:

```env
SECRET_KEY=your_secret_key
DEBUG=True
DATABASE_URL=postgresql://user:password@localhost:5432/bookshelf
GOOGLE_API_KEY=your_gemini_api_key
EMBEDDING_DIMENSIONS=768
```

`GOOGLE_API_KEY` is required at import time — `chat/services.py` raises `ValueError` on startup if it is missing.

## Architecture

### Django Apps

- **`books/`** — Core domain: `Book` (catalog), `UserBook` (per-user shelf entry with status/rating/notes), `BookEmbedding` (pgvector embeddings). Views mix class-based (`BookListView`, `UserBookshelfView`) and function-based views for HTMX partials.
- **`chat/`** — AI chatbot: `ChatAPIView` delegates to `AIService` in `chat/services.py`.
- **`accounts/`** — Custom auth backend (`EmailBackend`) that authenticates by email instead of username.

### Settings Structure

`bookshelf/settings/` has three layers:
- `base.py` — shared config, reads `DATABASE_URL` via `dj-database-url` (defaults to SQLite)
- `local.py` — local overrides
- `dev.py` — production/Railway config (`DEBUG=False`, enforces PostgreSQL, WhiteNoise static files, HSTS)

The active settings module is selected via the `DJANGO_SETTINGS_MODULE` env var.

### AI / RAG Pipeline (`chat/services.py`)

`AIService` implements an advanced RAG flow over the user's personal bookshelf:

1. **Intent classification** — small talk is handled directly, bypassing all DB queries.
2. **Recency short-circuit** — questions like "what did I last read?" sort by `date_updated` rather than vector distance, since recency is a metadata property.
3. **Query rewriting** — the LLM expands the question into 2–3 semantic variants.
4. **Vector search** — each variant is embedded and searched against the user's `BookEmbedding` rows via `CosineDistance` (pgvector). Status/genre filters are applied at the ORM level before the search.
5. **LLM reranking** — candidates are scored 0–10 for relevance; top `k=6` go to the answer prompt.

`_embeddings` and `_llm` are module-level singletons (initialized once per worker). The model is `gemini-2.5-flash`; embeddings use `models/gemini-embedding-001` at 768 dimensions.

### Embedding Sync

`books/signals.py` wires a `post_save` signal on `UserBook` to call `AIService.add_user_book_to_vectorstore()`, keeping `BookEmbedding` in sync whenever a shelf entry is created or updated. The `BookEmbedding` table has an IVFFlat cosine index created in migration `books/0002_bookembedding`.

### Frontend

Pages use **HTMX** for partial updates (book list filtering, modal interactions, row swaps after edits). Views detect `HX-Request` headers to return partial templates instead of full pages. The admin UI uses **Jazzmin**. Static files are served by **WhiteNoise** in production.

### Authentication

Users can log in with either their username or email (`accounts/authentication.py`). Both `EmailBackend` and Django's default `ModelBackend` are active.

### Streaming

`AIService.stream_ask()` yields tokens via LangChain's `chain.stream(...)`. It is implemented but currently commented out in `ChatAPIView`; to enable it, return a `StreamingHttpResponse` instead of `JsonResponse`.
