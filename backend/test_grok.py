from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

client = OpenAI(
    api_key=os.getenv("XAI_API_KEY"),
    base_url="https://api.x.ai/v1",
)

model = os.getenv("LLM_MODEL", "openai/gpt-oss-120b")

response = client.chat.completions.create(
    model=model,

    messages=[
        {
            "role": "user",
            "content": "Hello, introduce yourself in one sentence."
        }
    ]
)

print(response.choices[0].message.content)