import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    # Try to find .env manually if load_dotenv fails in some environments
    import pathlib

    env_path = pathlib.Path(__file__).parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                if line.startswith("GOOGLE_API_KEY="):
                    api_key = line.strip().split("=", 1)[1]
                    break

if not api_key:
    print("Error: GOOGLE_API_KEY not found in environment or .env file.")
else:
    try:
        genai.configure(api_key=api_key)

        print(f"Listing available models for API Key: {api_key[:5]}...")
        print("-" * 40)
        found_any = False
        for m in genai.list_models():
            found_any = True
            print(f"Name: {m.name}")
            print(f"Description: {m.description}")
            print(f"Supported methods: {m.supported_generation_methods}")
            print("-" * 40)

        if not found_any:
            print(
                "No models found. Check your API key permissions and region availability."
            )

    except Exception as e:
        print(f"Error listing models: {e}")
