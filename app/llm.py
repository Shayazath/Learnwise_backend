
import os

from dotenv import load_dotenv
from groq import Groq
from groq import APIConnectionError, APIStatusError, APITimeoutError, RateLimitError

load_dotenv()


class LLMUnavailableError(RuntimeError):
    pass


GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY is missing from environment variables.")

client = Groq(
    api_key=GROQ_API_KEY,
    timeout=120.0,
    max_retries=2,
)


def generate(prompt: str, system: str | None = None) -> str:
    messages = []

    if system:
        messages.append({
            "role": "system",
            "content": system
        })

    messages.append({
        "role": "user",
        "content": prompt
    })

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            temperature=0.3,
            max_completion_tokens=2048,
        )

        answer = response.choices[0].message.content

        if not answer or not answer.strip():
            raise LLMUnavailableError(
                "The AI model returned an empty response."
            )

        return answer.strip()

    except RateLimitError as exc:
        raise LLMUnavailableError(
            "Groq API rate limit reached. Please try again later."
        ) from exc

    except (APIConnectionError, APITimeoutError) as exc:
        raise LLMUnavailableError(
            "Could not connect to Groq API. Please try again."
        ) from exc

    except APIStatusError as exc:
        raise LLMUnavailableError(
            f"Groq API error ({exc.status_code}). Please try again later."
        ) from exc
