# Personal Bookshelf

A Django-based personal bookshelf application that allows users to track the books they want to read, are currently reading, and have already read. It features a modern interface, user authentication, and an AI-powered chatbot that can answer questions about the user's reading history.

## Features

- **User Authentication**: Secure login and registration system.
- **Book Management**: Add, edit, and delete books from your personal library.
- **Reading Status**: Track books with three statuses: "Want to Read", "Reading", and "Read".
- **Rating System**: Rate books on a scale of 1 to 5 stars.
- **Notes**: Add personal notes to each book.
- **AI Chatbot**: An intelligent assistant powered by Gemini that can answer questions about your reading habits, recommend books, and provide information based on your library.

## Tech Stack

- **Backend**: Django
- **Database**: PostgreSQL with `pgvector` extension for vector similarity search
- **AI/ML**: Google Gemini (Embeddings and Chat)
- **Frontend**: HTML, CSS, JavaScript
- **Deployment**: Docker (optional, for containerized deployment)

## Prerequisites

- Python 3.8+
- PostgreSQL 13+
- Docker (optional)

## Installation

1.  **Clone the repository**
    ```bash
    git clone https://github.com/JoseSholly/personal-bookshelf.git
    cd personal-bookshelf
    ```

2.  **Set up a virtual environment**
    ```bash
    python -m venv venv
    source venv/bin/activate  # Windows: venv\Scripts\activate
    ```

3.  **Install dependencies**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Environment Configuration**
    Create a `.env` file in the root directory with the following variables:
    ```env
    SECRET_KEY=your_secret_key
    DEBUG=True
    DATABASE_URL=postgresql://user:password@localhost:5432/bookshelf
    GOOGLE_API_KEY=your_gemini_api_key
    EMBEDDING_DIMENSIONS=768
    ```

5.  **Database Setup**
    Apply the database migrations:
    ```bash
    python manage.py migrate
    ```

6.  **Create Superuser** (optional)
    ```bash
    python manage.py createsuperuser
    ```

7.  **Run the Development Server**
    ```bash
    python manage.py runserver
    ```
    The application will be available at `http://localhost:8000`.

## Docker Deployment

To run the application using Docker:

1.  **Build the Docker image**
    ```bash
    docker-compose build
    ```

2.  **Start the containers**
    ```bash
    docker-compose up -d
    ```

3.  **Apply migrations**
    ```bash
    docker-compose exec web python manage.py migrate
    ```

## Usage

- **Login**: Use the credentials created during setup or registration.
- **Add Books**: Navigate to "Add Book" to manually enter book details.
- **Chat**: Click the "Chat" button in the bottom-right corner to talk to the AI assistant.

## AI Chatbot

The chatbot uses Google Gemini to understand and answer questions about your book collection. You can ask:
- "What sci-fi books have I read?"
- "How many books do I have left to read?"
- "What's the last book I finished?"
- "Recommend a fantasy book I might like."

## License

MIT License
