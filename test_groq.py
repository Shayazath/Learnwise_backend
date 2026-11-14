
import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

client = Groq(
    api_key=os.environ["GROQ_API_KEY"],
    timeout=30.0,
    max_retries=1,
)

response = client.chat.completions.create(
    model=os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"),
    messages=[
        {
            "role": "user",
            "content": "Explain RAG in two simple sentences."
        }
    ],
    max_completion_tokens=300,
)

print(response.choices[0].message.content)
