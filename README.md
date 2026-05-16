# Personal Bookshelf

A Django-based personal bookshelf application that allows users to track the books they want to read, are currently reading, and have already read. It features a modern interface, user authentication, and an AI-powered chatbot that can answer questions about the user's reading history.

## Features

- **User Authentication**: Register and log in with either your username or email address.
- **Book Catalog**: Browse a seeded catalog of 50 classic books with search and pagination.
- **Reading Status**: Track books with three statuses: "Want to Read", "Reading", and "Read".
- **Rating & Notes**: Rate books 1–5 stars and add personal notes.
- **AI Chatbot**: An intelligent assistant powered by Google Gemini and LangChain that answers questions about your reading habits, recommends books, and summarises your history using an advanced RAG pipeline.

## Tech Stack

- **Backend**: Django 5.2
- **Database**: PostgreSQL with `pgvector` extension for vector similarity search
- **AI/ML**: Google Gemini (`gemini-2.5-flash` + `gemini-embedding-001`), LangChain
- **Frontend**: HTMX (partial page updates), Jazzmin (admin UI)
- **Static Files**: WhiteNoise
- **Deployment**: Gunicorn / Railway

## Prerequisites

- Python 3.8+
- PostgreSQL 13+ with the `pgvector` extension

## Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/JoseSholly/personal-bookshelf.git
   cd personal-bookshelf
   ```

2. **Set up a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment configuration**

   Create a `.env` file in the project root:
   ```env
   SECRET_KEY=your_secret_key
   DEBUG=True
   DATABASE_URL=postgresql://user:password@localhost:5432/bookshelf
   GOOGLE_API_KEY=your_gemini_api_key
   EMBEDDING_DIMENSIONS=768
   ```

   > `GOOGLE_API_KEY` is required — the app will refuse to start without it.

5. **Run migrations**
   ```bash
   python manage.py migrate
   ```

6. **Seed the book catalog** (optional — adds 50 classic books)
   ```bash
   python manage.py seed_books
   ```

7. **Create a superuser** (optional)
   ```bash
   python manage.py createsuperuser
   ```

8. **Start the development server**
   ```bash
   python manage.py runserver
   ```
   The application will be available at `http://localhost:8000`.

## Usage

- **Login**: Use your username or email address.
- **Browse Books**: Navigate to `/books/` to search and filter the catalog.
- **Your Shelf**: View, edit, and remove books from your personal shelf at `/books/shelf/`.
- **Chat**: Click the chat button in the bottom-right corner to ask the AI assistant anything about your reading history.

## AI Chatbot

The chatbot uses an advanced Retrieval-Augmented Generation (RAG) pipeline backed by pgvector:

1. **Intent classification** — greetings and small talk are handled directly without touching the database.
2. **Recency short-circuit** — questions like "what did I last read?" are answered by sorting on `date_updated` rather than vector distance.
3. **Query rewriting** — the LLM rewrites the question into 2–3 keyword-rich semantic variants.
4. **Vector search** — each variant is embedded and searched against the user's book embeddings using cosine distance, with optional status/genre filters applied at the ORM level.
5. **LLM reranking** — candidates are scored 0–10 for relevance; the top 6 are passed to the answer prompt.

Embeddings are stored directly in PostgreSQL via `pgvector` (no separate vector store needed).

Example questions:
- "What sci-fi books have I read?"
- "How many books do I have left to read?"
- "What's the last book I finished?"
- "Recommend a fantasy book I might like."

## Production Deployment (Railway)

Set `DJANGO_SETTINGS_MODULE=bookshelf.settings.dev` and provide the following env vars on Railway:

```env
SECRET_KEY=...
DATABASE_URL=...      # Railway Postgres (pgvector is supported by default)
GOOGLE_API_KEY=...
ALLOWED_HOSTS=your-app.railway.app
```

The `dev.py` settings enable WhiteNoise static file compression, HSTS, and secure cookie flags automatically.

## License

MIT License
