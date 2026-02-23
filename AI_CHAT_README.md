# AI Chat with LangChain & Google Gemini

This document explains the architecture and implementation of the AI-powered chat assistant in the Personal Bookshelf application.

## Overview

The chat feature allows users to ask questions about their book collection, get reading recommendations, and summarise their reading history. It uses **Google Gemini** for both embeddings and language generation, orchestrated by **LangChain**, with **pgvector** (a PostgreSQL extension) as the vector store — meaning embeddings live in the same database as the rest of the app.

The retrieval pipeline is **advanced RAG**: every question goes through query rewriting, parallel vector search, deduplication, and LLM-based reranking before the answer is generated. Recency-specific questions (e.g. *"what did I last read?"*) are short-circuited to a direct `date_updated` sort rather than vector search.

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
User submits question (POST)
  → chat/views.py (ChatAPIView)
  → AIService(user).ask(question)
  → get_context()   ← advanced RAG pipeline (see below)
  → Gemini LLM      ← generates answer using retrieved context
  → JsonResponse returned to client
```

> **Note:** A `stream_ask()` method also exists on `AIService` and yields tokens one-by-one via `chain.stream(...)`. Streaming is currently commented out in `ChatAPIView` but can be re-enabled by returning a `StreamingHttpResponse`.

### 2. Module-level Singletons

Heavy objects are initialised once per worker at import time:

```python
_embeddings = GoogleGenerativeAIEmbeddings(
    model="models/gemini-embedding-001",
    dimensions=768,  # controlled by EMBEDDING_DIMENSIONS env var
)

_llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0.5,
    top_p=0.9,
)
```

### 3. Context Retrieval — Advanced RAG Pipeline

`get_context(question, k=6)` implements a multi-stage retrieval strategy:

```
Question
  │
  ├─ Is it a recency question?  ──YES──► Sort by date_updated (metadata, not vector)
  │  (last read / most recent / just finished …)
  │
  └─ NO
       │
       ├─ 1. Extract explicit filters
       │     status_filter  (read / reading / want_to_read)
       │     genre_filter   (sci-fi / fantasy / mystery …)
       │
       ├─ 2. Query rewriting (LLM)
       │     Original question → 2–3 keyword-rich variants
       │
       ├─ 3. Parallel vector search (per rewritten query)
       │     CosineDistance on BookEmbedding, over-retrieve top 12 each
       │
       ├─ 4. Deduplicate by BookEmbedding.id
       │
       └─ 5. LLM reranking
             Score each candidate 0–10 for relevance
             Return top k docs
```

#### 3a. Recency Short-circuit

Questions that mention phrases like *"last read"*, *"most recent"*, *"just finished"* etc. are detected by `_is_recency_query()` and bypass vector search entirely:

```python
if self._is_recency_query(question):
    recency_qs = BookEmbedding.objects.filter(user=self.user)
    if status_filter:
        recency_qs = recency_qs.filter(user_book__status=status_filter)
    else:
        recency_qs = recency_qs.filter(user_book__status="read")

    recent_docs = list(recency_qs.order_by("-user_book__date_updated")[:k])
    return "\n\n".join(r.content for r in recent_docs)
```

> Vector search cannot answer *"which was last?"* because recency is a metadata property, not a semantic concept.

#### 3b. Query Rewriting

The `QUERY_REWRITE_PROMPT` asks the LLM to expand the user's question into 2–3 keyword-rich variants tuned for semantic search (focusing on status, genre, rating, `date_updated`, author, title):

```python
rewrite_chain = QUERY_REWRITE_PROMPT | _llm | StrOutputParser()
rewritten = rewrite_chain.invoke({"question": question})
queries = [q.strip() for q in rewritten.split("\n") if q.strip()][:3]
```

#### 3c. Vector Search with Filters

For each rewritten query, a `CosineDistance` search is run against the user's own `BookEmbedding` rows (user isolation is enforced at the ORM level):

```python
for q in queries:
    vec = _embed_text(q, is_query=True)
    results = base_qs.annotate(
        distance=CosineDistance("embedding", vec)
    ).order_by("distance")[:12]   # over-retrieve
    all_docs.extend(results)
```

- Status and genre filters are applied to the base queryset **before** the vector search.
- Retrieving `12` candidates per query (over-retrieval) ensures the reranker has enough material to work with.

#### 3d. LLM Reranking

Each unique candidate is scored 0–10 for relevance to the original question using `RERANK_PROMPT`:

```python
score_chain = RERANK_PROMPT | _llm | StrOutputParser()
score = int(score_chain.invoke({"question": question, "content": doc.content}))
```

The top `k` documents (by score) are passed as context to the final answer generation.

### 4. Embedding Upsert

When a user adds or updates a book, the `post_save` signal on `UserBook` calls `add_user_book_to_vectorstore()`. The document text now includes **genre**, **publication year**, and **last updated timestamp** so that the vector content can support richer semantic and metadata queries:

```python
def add_user_book_to_vectorstore(self, instance) -> None:
    doc_text = (
        f"Book: {instance.book.title} by {instance.book.author}. "
        f"Genre: {instance.book.genre}. "
        f"Year: {instance.book.publication_year or 'unknown'}. "
        f"Status: {instance.status}. "
        f"Rating: {instance.rating or 'None'}. "
        f"Notes: {instance.notes or 'No notes'}. "
        f"Last updated: {instance.date_updated.strftime('%Y-%m-%d %H:%M') if instance.date_updated else 'unknown'}."
    )
    vector = _embed_text(doc_text)

    BookEmbedding.objects.update_or_create(
        user_book=instance,
        defaults={"user": instance.user, "content": doc_text, "embedding": vector},
    )
```

`update_or_create` ensures that re-saving a book always refreshes its embedding, keeping the vector store in sync with the latest metadata.

### 5. Response Handling

- **`ask(question)`**: Returns a complete answer string in a single `JsonResponse`. This is the active path.
- **`stream_ask(question)`**: Yields answer chunks token-by-token via `chain.stream(...)`. Available but currently commented out in the view; can be enabled by returning a `StreamingHttpResponse`.
- User isolation is always enforced at the ORM level — no cross-user data leakage is possible.

---

## Setup & Configuration

### Environment Variables

Add the following to your `.env`:

```env
GOOGLE_API_KEY=your_gemini_api_key_here
EMBEDDING_DIMENSIONS=768   # optional; defaults to 768
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

| Parameter | Current Value | Notes |
|---|---|---|
| `k` (top docs returned) | `6` | Increase for broader context; decrease to reduce latency |
| Over-retrieve per query | `12` | Candidates fetched per rewritten query before reranking |
| Rewritten queries | up to `3` | Controlled by the query rewrite LLM output |
| IVFFlat `lists` | `100` | Tune to `sqrt(rows)` once the table exceeds ~1 M rows |
| `temperature` | `0.5` | Lower = more factual; higher = more creative |
| `top_p` | `0.9` | Controls diversity of LLM output |
| `EMBEDDING_DIMENSIONS` | `768` | Must match the pgvector column dimension in the migration |

> **LLM call budget per user query:** up to 1 (rewrite) + N×1 (rerank, where N = unique candidates) + 1 (answer) calls. For a typical bookshelf, this is manageable, but consider caching or disabling reranking at scale.
