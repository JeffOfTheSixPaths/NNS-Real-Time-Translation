# %%
from google import genai
import os
# The client gets the API key from the environment variable `GEMINI_API_KEY`.
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

response = client.models.generate_content(
    model="gemini-2.5-flash", contents="Translate the following from spanish to english. Do not say anything other than the translation: Apoyo el sufragio femenino"
)
print(response.text)




