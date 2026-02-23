import os
import logging
from typing import List, Optional

from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from pgvector.django import CosineDistance

load_dotenv()

logger = logging.getLogger(__name__)

# ─── Module-level singletons ────────────────────────────────────────────────

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY environment variable is not set")

EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIMENSIONS", "768"))

# Shared models
_embeddings = GoogleGenerativeAIEmbeddings(
    model="models/gemini-embedding-001",
    google_api_key=GOOGLE_API_KEY,
    dimensions=EMBEDDING_DIM,
)

_llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0.5,
    top_p=0.9,
    google_api_key=GOOGLE_API_KEY,
)

# ─── Prompts ────────────────────────────────────────────────────────────────

RETRIEVAL_PROMPT = PromptTemplate.from_template(
    """You are a concise book companion who knows the user's reading history.

Rules:
- Keep answers short: 100–400 characters when possible.
- Never exceed 600 characters unless the question clearly needs detail.
- Use bullet points or short paragraphs — avoid long blocks.
- Be spoiler-free unless explicitly asked for spoilers.
- Personalize using the provided context when relevant.
- For general questions, answer briefly using your knowledge.

User context (relevant excerpts only):
{context}

Question: {question}

Answer (stay concise):"""
)

QUERY_REWRITE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You help improve retrieval from a user's personal bookshelf.
The data contains: title, author, genre, year, status (want_to_read/reading/read), rating (0-5 or null), short user notes, and date_updated (when the entry was last changed).

Rewrite the original question into 2–3 short, keyword-rich versions optimized for semantic search.
Focus especially on status, rating level, genre, date_updated, and any mentioned books/authors.
Output only the rewritten queries, one per line.""",
        ),
        ("human", "{question}"),
    ]
)

RERANK_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You are a relevance judge.
Given a user question and a book entry, assign a relevance score 0–10.
- 10 = perfectly matches what the user is asking for
- 5  = somewhat related
- 0  = completely unrelated

Output ONLY the score as integer.""",
        ),
        ("human", "Question: {question}\n\nBook entry:\n{content}\n\nScore:"),
    ]
)

# ─── Helpers ────────────────────────────────────────────────────────────────


def _embed_text(text: str, is_query: bool = False) -> List[float]:
    task = "retrieval_query" if is_query else "retrieval_document"
    try:
        return _embeddings.embed_query(
            text, task_type=task, output_dimensionality=EMBEDDING_DIM
        )
    except Exception as e:
        logger.error(f"Embedding failed: {e}", exc_info=True)
        return [0.0] * EMBEDDING_DIM  # fallback


class AIService:
    """Service to handle AI chat interactions using LangChain + pgvector."""

    def __init__(self, user):
        self.user = user

    def _log_retrieved_docs(self, docs: List, label: str = "Retrieved"):
        if not docs:
            logger.info(f"{label}: no documents found")
            return

        logger.info(f"{label} ({len(docs)} documents):")
        for i, doc in enumerate(docs, 1):
            distance = getattr(doc, "distance", None)

            dist_str = f"{distance:.4f}" if distance is not None else "—     "

            logger.debug(f"  {i}. distance={dist_str} | {doc.content[:180]}...")
    def _parse_status_filter(self, question: str) -> Optional[str]:
        q = question.lower()
        # Check more specific phrases first to avoid substring collisions
        # ("reading" contains "read", so check for reading/currently reading first)
        if any(w in q for w in ["currently reading", "still reading", "am reading"]):
            return "reading"
        if any(w in q for w in ["want to read", "to-read", "plan to read", "future"]):
            return "want_to_read"
        if any(
            w in q
            for w in [
                "finished",
                "completed",
                "already read",
                "have read",
                "last read",
                "most recent",
                "recently read",
            ]
        ):
            return "read"
        return None

    def _is_recency_query(self, question: str) -> bool:
        """Detect questions specifically about the most recent book."""
        q = question.lower()
        recency_phrases = [
            "last read",
            "most recent",
            "recently read",
            "latest read",
            "last book",
            "latest book",
            "most recently",
            "just finished",
            "last finished",
            "just read",
        ]
        return any(phrase in q for phrase in recency_phrases)

    def _parse_genre_filter(self, question: str) -> Optional[str]:
        q = question.lower()
        common_genres = [
            "sci-fi",
            "science fiction",
            "fantasy",
            "mystery",
            "thriller",
            "romance",
            "non-fiction",
        ]
        for g in common_genres:
            if g in q:
                return g.replace(" ", "").replace("-", "")  # normalize
        return None

    def get_context(self, question: str, k: int = 6) -> str:
        """Improved retrieval with query rewriting + filtering + reranking"""
        from books.models import BookEmbedding

        # 1. Short-circuit for recency questions — order by date_updated, not cosine distance.
        #    Vector search cannot reliably answer "which was last?" because recency is
        #    a metadata property, not a semantic one.
        if self._is_recency_query(question):
            status_filter = self._parse_status_filter(question)
            recency_qs = BookEmbedding.objects.filter(user=self.user)
            if status_filter:
                recency_qs = recency_qs.filter(user_book__status=status_filter)
            else:
                # Default to books that have been read when asking about "last read"
                recency_qs = recency_qs.filter(user_book__status="read")

            recent_docs = list(recency_qs.order_by("-user_book__date_updated")[:k])
            self._log_retrieved_docs(
                recent_docs, "Recency query — ordered by date_updated"
            )
            return "\n\n".join(r.content for r in recent_docs) if recent_docs else ""

        # 2. Try to extract explicit filters from question
        status_filter = self._parse_status_filter(question)
        genre_filter = self._parse_genre_filter(question)

        # 3. Generate better retrieval queries
        try:
            rewrite_chain = QUERY_REWRITE_PROMPT | _llm | StrOutputParser()
            rewritten = rewrite_chain.invoke({"question": question})
            queries = [q.strip() for q in rewritten.split("\n") if q.strip()][:3]
            if not queries:
                queries = [question]
            logger.debug(f"Rewritten queries: {queries}")
        except Exception as e:
            logger.warning(f"Query rewrite failed: {e}")
            queries = [question]

        # 4. Retrieve candidates (over-retrieve)
        all_docs = []
        base_qs = BookEmbedding.objects.filter(user=self.user)

        if status_filter:
            base_qs = base_qs.filter(user_book__status=status_filter)
        if genre_filter:
            base_qs = base_qs.filter(user_book__book__genre__icontains=genre_filter)

        for q in queries:
            try:
                vec = _embed_text(q, is_query=True)
                results = base_qs.annotate(
                    distance=CosineDistance("embedding", vec)
                ).order_by("distance")[
                    :12
                ]  # over-retrieve
                all_docs.extend(results)
            except Exception as e:
                logger.error(f"Vector search failed for query '{q}': {e}")

        # Deduplicate
        unique = {r.id: r for r in all_docs}.values()
        self._log_retrieved_docs(unique, "Candidates before rerank")

        # 5. Lightweight reranking with LLM
        ranked = []
        for doc in unique:
            try:
                score_chain = RERANK_PROMPT | _llm | StrOutputParser()
                raw_score = score_chain.invoke(
                    {"question": question, "content": doc.content}
                ).strip()
                score = int(raw_score) if raw_score.isdigit() else 5
                ranked.append((score, doc))
            except Exception as e:
                logger.error(f"Reranking failed for doc '{doc.content}': {e}")
                ranked.append((3, doc))  # fallback

        # Sort descending by score, then take top k
        ranked.sort(key=lambda x: x[0], reverse=True)
        top_docs = [doc for _, doc in ranked[:k]]

        self._log_retrieved_docs(top_docs, "After reranking")

        if not top_docs:
            return ""

        return "\n\n".join(r.content for r in top_docs)

    def ask(self, question: str) -> str:
        """Process the user's question and return a single answer."""
        context = self.get_context(question)
        chain = RETRIEVAL_PROMPT | _llm | StrOutputParser()
        try:
            answer = chain.invoke({"context": context, "question": question})
            return answer
        except Exception as e:
            logger.error(f"Generation failed: {e}", exc_info=True)
            return "Sorry, I couldn't generate an answer right now."

    def stream_ask(self, question: str):
        """Stream the answer token by token."""
        context = self.get_context(question)
        chain = RETRIEVAL_PROMPT | _llm
        try:
            for chunk in chain.stream({"context": context, "question": question}):
                yield chunk.content
        except Exception as e:
            logger.error(f"Streaming failed: {e}")
            yield "Error during streaming."

    def add_user_book_to_vectorstore(self, instance) -> None:
        """Embed and upsert UserBook entry into pgvector."""
        from books.models import BookEmbedding

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
            defaults={
                "user": instance.user,
                "content": doc_text,
                "embedding": vector,
            },
        )
        logger.info(
            "Upserted embedding for UserBook %s (user=%s)", instance.id, self.user.id
        )
