import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
client = Groq()
model = os.environ.get("MODEL")
response = client.chat.completions.create(
    messages=[{"role": "user", "content": "say hi"}],
    model=model,
)
print(response.choices[0].message.content)
