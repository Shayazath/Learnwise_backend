
import os
import time

from dotenv import load_dotenv
from google import genai
from google.genai.errors import ServerError, ClientError

load_dotenv()

client = genai.Client(
    api_key=os.environ["GEMINI_API_KEY"]
)

model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

for attempt in range(3):
    try:
        print(f"Attempt {attempt + 1}: Sending request to Gemini model '{model}'...")
        response = client.models.generate_content(
            model=model,
            contents="Explain RAG in two simple sentences."
        )

        print("\nGemini response:")
        print(response.text)
        break

    except ServerError as error:
        if attempt == 2:
            print("Gemini is currently unavailable. Try again later.")
            raise

        wait_time = 2 ** (attempt + 1)
        print(f"Gemini unavailable. Retrying in {wait_time} seconds...")
        time.sleep(wait_time)

    except ClientError:
        print("Gemini request failed. Check your API key, model and request.")
        raise
