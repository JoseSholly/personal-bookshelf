# AI Chat with LangChain & Google Gemini

This document explains the architecture and implementation of the AI-powered chat assistant in the Personal Bookshelf application.

## Overview

The chat feature allows users to ask questions about their book collection, get reading recommendations, and summarize their reading history. It leverages **Google Gemini** for both embeddings and natural language generation, orchestrated by **LangChain**.

## Technology Stack

-   **Backend Framework**: Django
-   **AI Orchestration**: LangChain
-   **LLM (Large Language Model)**: Google Gemini (`gemini-2.5-flash`)
-   **Embeddings**: Google Generative AI Embeddings (`models/gemini-embedding-001`)
-   **Vector Store**: ChromaDB (Persistent local storage)
-   **Frontend**: HTML, Tailwind CSS, HTMX (for dynamic updates)

## Implementation Details

The core logic is modularized within the `chat/services.py` file, utilizing the `AIService` class.

### 1. Request Handling
When a user submits a question via the chat interface:
-   The request is sent to the `chat_api` endpoint (`chat/views.py`).
-   The view instantiates `AIService` with the current user.
-   The service's `ask(question)` method is called.

### 2. AIService Architecture
The `AIService` class encapsulates all AI-related logic:

-   **Initialization**: Sets up Google Gemini embeddings, Chat Model, and connects to the user-specific ChromaDB collection.
-   **Context Retrieval**: The `get_context(question)` method retrieves the top relevant documents (`k=6`) from the user's vector store.
-   **Prompt Generation**: Uses a predefined template to instruct the AI to be a concise book companion.
-   **Response Generation**: Chains the prompt and LLM to generate an answer.

### 3. Embeddings & Vector Search (RAG)
To provide context-aware answers, we use **Retrieval-Augmented Generation (RAG)**.

```python
# From chat/services.py

def get_context(self, question, k=6):
    """Retrieve relevant context from the vector store."""
    retriever = self.vectorstore.as_retriever(
        search_kwargs={"k": k, "filter": {"user_id": self.user.id}}
    )
    docs = retriever.invoke(question)
    return "\n\n".join([d.page_content for d in docs])
```

-   **User Isolation**: Each user has a unique collection name (`user_{id}_bookshelf`) or filtered search to ensure they only query their own data.

### 4. Vector Store Maintenance
The vector store (`./chroma_db`) is automatically updated whenever a user adds or updates a book in their shelf via Django signals.

-   **Signal Handler**: `books/signals.py` listens for `post_save` on `UserBook`.
-   **Delegation**: The signal calls `AIService.add_user_book_to_vectorstore(instance)`.

```python
# From chat/services.py

def add_user_book_to_vectorstore(self, instance):
    """Embed and add a UserBook instance to the vector store."""
    doc_text = f"Book: {instance.book.title}..."
    # ... adds to ChromaDB
```

### 5. Response Handling
-   The generated answer is returned to the frontend.
-   If the request is from **HTMX**, we render a partial HTML template (`chat/ai_response.html`) that gets inserted directly into the chat stream.
-   Otherwise, a JSON response is returned.

## Setup & Configuration

To run this locally, ensure you have the following environment variables in your `.env` file:

```env
GOOGLE_API_KEY=your_gemini_api_key_here
```

## Vector Store Maintenance

The vector store (`./chroma_db`) is automatically updated whenever a user adds or updates a book in their shelf (handled via Django signals, ensuring the AI always has the latest data).
