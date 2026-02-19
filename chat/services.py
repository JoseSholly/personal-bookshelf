# services.py
from django.conf import settings
import os
from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.prompts import PromptTemplate
import chromadb

load_dotenv()

# ─── Module-level (singleton) heavy objects ──────────────────────────────
# These are loaded only once when the module is first imported (per worker)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY environment variable is not set")


# Embeddings – shared across all instances
embeddings = GoogleGenerativeAIEmbeddings(
    model="models/gemini-embedding-001",
    google_api_key=GOOGLE_API_KEY,
)


# Shared persistent Chroma client
_chroma_client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)


# LLM – shared, with controlled output length
_llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0.6,
    top_p=0.9,
    google_api_key=GOOGLE_API_KEY,
    max_output_tokens=450,
)


# Prompt template – also shared
_PROMPT_TEMPLATE = PromptTemplate.from_template(
    """You are a concise book companion who knows the user's reading history.

Rules:
- Keep answers short: 100–400 characters when possible.
- Never exceed 600 characters unless the question clearly needs detail.
- Use bullet points or short paragraphs — avoid long blocks.
- Be spoiler-free unless the user explicitly asks for spoilers.
- Personalize using the provided context when relevant.
- For general questions, answer briefly using your knowledge.

User context (relevant excerpts only):
{context}

Question: {question}

Answer (stay concise):"""
)


class AIService:
    """Service to handle AI chat interactions using LangChain + Google Gemini."""

    def __init__(self, user):
        self.user = user
        self.vectorstore = self._get_vectorstore()

    def _get_vectorstore(self):
        """Get or create per-user Chroma collection using shared client."""
        collection_name = f"user_{self.user.id}_bookshelf"

        return Chroma(
            client=_chroma_client,  # ← shared client
            collection_name=collection_name,
            embedding_function=embeddings,  # ← shared embeddings
        )

    def get_context(self, question, k=4):  # ← reduced from 6 → 4
        """Retrieve relevant context from the vector store."""
        retriever = self.vectorstore.as_retriever(
            search_kwargs={"k": k, "filter": {"user_id": self.user.id}}
        )
        docs = retriever.invoke(question)
        return "\n\n".join(d.page_content for d in docs)

    def ask(self, question):
        """Process the user's question and generate an answer."""
        context = self.get_context(question)
        chain = _PROMPT_TEMPLATE | _llm  # ← uses shared LLM
        response = chain.invoke({"context": context, "question": question})
        return response.content

    def stream_ask(self, question):
        """Process the user's question and stream the answer."""
        context = self.get_context(question)
        chain = _PROMPT_TEMPLATE | _llm
        for chunk in chain.stream({"context": context, "question": question}):
            yield chunk.content

    def add_user_book_to_vectorstore(self, instance):
        """Embed and add a UserBook instance to the vector store."""
        doc_text = (
            f"Book: {instance.book.title} by {instance.book.author}. "
            f"Status: {instance.status}. "
            f"Rating: {instance.rating or 'None'}. "
            f"Notes: {instance.notes or 'No notes'}. "
            f"Description: {instance.book.description}"
        )

        unique_id = f"userbook_{instance.id}"

        self.vectorstore.add_texts(
            texts=[doc_text],
            metadatas=[
                {
                    "user_id": self.user.id,
                    "book_id": instance.book.id,
                    "type": "user_book",
                }
            ],
            ids=[unique_id],
        )
