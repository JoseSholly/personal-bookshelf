from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.prompts import PromptTemplate
import os
from dotenv import load_dotenv
import chromadb

load_dotenv()


class AIService:
    """Service to handle AI chat interactions using LangChain and Google Gemini."""

    def __init__(self, user):
        self.user = user
        self.api_key = os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is not set")

        self.embeddings = self._get_embeddings()
        self.vectorstore = self._get_vectorstore()
        self.llm = self._get_chat_model()

    def _get_embeddings(self):
        """Initialize Google Generative AI Embeddings."""
        return GoogleGenerativeAIEmbeddings(
            model="models/gemini-embedding-001",
            google_api_key=self.api_key,
        )

    def _get_vectorstore(self):
        """Initialize ChromaDB vector store for the specific user."""
        from django.conf import settings

        client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)

        collection_name = f"user_{self.user.id}_bookshelf"

        # Get or create collection
        return Chroma(
            client=client,
            collection_name=collection_name,
            embedding_function=self.embeddings,
        )

    def _get_chat_model(self):
        """Initialize Google Gemini Chat Model."""
        return ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0.6,
            top_p=0.9,
            api_key=self.api_key,
        )

    def _get_prompt_template(self):
        """Define the prompt template for the AI."""
        return PromptTemplate.from_template(
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

    def get_context(self, question, k=6):
        """Retrieve relevant context from the vector store."""
        retriever = self.vectorstore.as_retriever(
            search_kwargs={"k": k, "filter": {"user_id": self.user.id}}
        )
        docs = retriever.invoke(question)
        return "\n\n".join([d.page_content for d in docs])

    def ask(self, question):
        """Process the user's question and generate an answer."""
        context = self.get_context(question)
        prompt = self._get_prompt_template()
        chain = prompt | self.llm
        response = chain.invoke({"context": context, "question": question})
        return response.content

    def stream_ask(self, question):
        """Process the user's question and stream the answer."""
        context = self.get_context(question)
        prompt = self._get_prompt_template()
        chain = prompt | self.llm
        for chunk in chain.stream({"context": context, "question": question}):
            yield chunk.content

    def add_user_book_to_vectorstore(self, instance):
        """Embed and add a UserBook instance to the vector store."""
        doc_text = (
            f"Book: {instance.book.title} by {instance.book.author}. "
            f"Status: {instance.status}. Rating: {instance.rating or 'None'}. "
            f"Notes: {instance.notes or 'No notes'}. "
            f"Description: {instance.book.description}"
        )

        # Use the Django model ID as the Chroma ID to prevent duplicates
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
