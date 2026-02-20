# AI Chat with LangChain & Google Gemini

This document explains the architecture and implementation of the AI-powered chat assistant in the Personal Bookshelf application.

## Overview

The chat feature allows users to ask questions about their book collection, get reading recommendations, and summarise their reading history. It uses **Google Gemini** for both embeddings and language generation, orchestrated by **LangChain**, with **pgvector** (a PostgreSQL extension) as the vector store — meaning embeddings live in the same database as the rest of the app.

---

## Technology Stack

| Layer | Technology |
|---|---|
| Backend Framework | Django |
| AI Orchestration | LangChain |
| LLM | Google Gemini (`gemini-2.5-flash`) |
| Embeddings | Google Generative AI (`models/gemini-embedding-001`, 768 dimensions) |
| Vector Store | **pgvector** (PostgreSQL extension — replaces ChromaDB) |
| Frontend | HTML, Tailwind CSS, HTMX |

> **Why pgvector instead of ChromaDB?**  
> ChromaDB required a separate file-based store (and a Railway volume in production). pgvector stores vectors directly in PostgreSQL, eliminating the external dependency, simplifying deployment, and enabling SQL-level filtering and indexing.

---

## Data Model

Book embeddings are stored in the `BookEmbedding` model (`books/models.py`):

```python
class BookEmbedding(models.Model):
    user_book  = models.OneToOneField(UserBook, on_delete=models.CASCADE, related_name="embedding")
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name="book_embeddings")
    content    = models.TextField()          # plain text that was embedded
    embedding  = VectorField(dimensions=768) # pgvector column
    updated_at = models.DateTimeField(auto_now=True)
```

An **IVFFlat** index (cosine distance, `lists=100`) is created by migration `books/0002_bookembedding.py` for fast approximate nearest-neighbour search.

---

## Implementation Details

All AI logic lives in `chat/services.py` inside the `AIService` class.

### 1. Request Flow

```
User submits question
  → chat/views.py (chat_api)
  → AIService(user).stream_ask(question)  ← or .ask(question)
  → get_context()   ← pgvector similarity search
  → Gemini LLM      ← generates answer using retrieved context
  → response streamed back via HTMX
```

### 2. Module-level Singletons

Heavy objects are initialised once per worker at import time:

```python
_embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001", ...)
_llm        = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.6, ...)
```

### 3. Context Retrieval (RAG)

`get_context()` embeds the user's question and runs a **cosine similarity search** against that user's `BookEmbedding` rows using pgvector's `CosineDistance` operator:

```python
def get_context(self, question: str, k: int = 4) -> str:
    from books.models import BookEmbedding

    query_vector = _embed_text(question)

    results = (
        BookEmbedding.objects.filter(user=self.user)
        .annotate(distance=CosineDistance("embedding", query_vector))
        .order_by("distance")[:k]
    )
    return "\n\n".join(r.content for r in results)
```

- User isolation is enforced at the ORM level via `filter(user=self.user)` — no cross-user data leakage.
- Only a **single indexed SQL query** is needed; no external process.

### 4. Embedding Upsert

When a user adds or updates a book, the `post_save` signal on `UserBook` calls `add_user_book_to_vectorstore()`, which embeds the book text and upserts it into `BookEmbedding`:

```python
def add_user_book_to_vectorstore(self, instance) -> None:
    from books.models import BookEmbedding

    doc_text = (
        f"Book: {instance.book.title} by {instance.book.author}. "
        f"Status: {instance.status}. "
        f"Rating: {instance.rating or 'None'}. "
        f"Notes: {instance.notes or 'No notes'}. "
        f"Description: {instance.book.description}"
    )
    vector = _embed_text(doc_text)

    BookEmbedding.objects.update_or_create(
        user_book=instance,
        defaults={"user": instance.user, "content": doc_text, "embedding": vector},
    )
```

`update_or_create` ensures that re-saving a book always refreshes its embedding.

### 5. Response Handling

- **Streaming** (`stream_ask`): response chunks are yielded token-by-token via `chain.stream(...)` and pushed to the browser using HTMX's SSE / chunked transfer.
- **Non-streaming** (`ask`): returns a complete string; used for API/JSON responses.
- If the request is from HTMX, a partial HTML template (`chat/ai_response.html`) is rendered; otherwise a plain JSON response is returned.

---

## Setup & Configuration

### Environment Variables

Add the following to your `.env`:

```env
GOOGLE_API_KEY=your_gemini_api_key_here
```

No extra vector-store configuration is needed — pgvector runs inside your existing PostgreSQL database.

### Required Packages

```
pgvector==0.4.2
langchain-postgres==0.0.14
langchain-google-genai==4.2.0
langchain==1.2.10
```

Install with:

```bash
pip install -r requirements.txt
```

### Database Setup

The pgvector extension and the `BookEmbedding` table are created automatically by Django migrations:

```bash
python manage.py migrate
```

| Migration | What it does |
|---|---|
| `accounts/0002_auto_20260220_2115` | Installs the `vector` PostgreSQL extension (`CREATE EXTENSION IF NOT EXISTS vector`) |
| `books/0002_bookembedding` | Creates the `BookEmbedding` table and its IVFFlat cosine index |

---

## Deployment Notes

### Local (`bookshelf.settings.local`)
- Uses the local PostgreSQL database configured via `POSTGRESQL_DB_*` env vars.
- pgvector must be installed in that Postgres instance (`CREATE EXTENSION IF NOT EXISTS vector` — handled by migration).

### Production / Railway (`bookshelf.settings.dev`)
- Uses the `DATABASE_URL` env var (standard Railway Postgres).
- **No Railway volume or mount path needed** — embeddings are stored directly in the Postgres service.
- Ensure the Postgres service on Railway supports pgvector (Railway's managed Postgres does by default).

---

## Performance Tuning

| Parameter | Default | Notes |
|---|---|---|
| `k` (retrieved docs) | `4` | Increase for broader context; decrease to reduce latency |
| IVFFlat `lists` | `100` | Tune to `sqrt(rows)` once the table exceeds ~1 M rows |
| `temperature` | `0.6` | Lower = more factual; higher = more creative |
| `top_p` | `0.9` | Controls diversity of LLM output |
