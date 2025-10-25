# %%
from google import genai
import os

# The client gets the API key from the environment variable `GEMINI_API_KEY`.
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def translate_text(input_text: str, target_lang: str, input_lang: str = "auto") -> str:
    """
    Translate text using Google's Gemini model.
    
    Args:
        input_text (str): The text to translate
        target_lang (str): The target language code (e.g., 'en', 'es', 'fr', 'de')
        input_lang (str, optional): The input language code. Defaults to "auto" for auto-detection.
    
    Returns:
        str: The translated text
    """
    # Map of language codes to full names
    lang_names = {
        "en": "English",
        "es": "Spanish",
        "fr": "French",
        "de": "German",
        "zh": "Chinese",
        "auto": "the detected language"
    }

    # Get full language names
    from_lang = lang_names.get(input_lang, input_lang)
    to_lang = lang_names.get(target_lang, target_lang)

    # Construct the prompt
    if input_lang == "auto":
        prompt = f"Translate the following text to {to_lang}. Only return the translation, nothing else: {input_text}"
    else:
        prompt = f"Translate the following {from_lang} text to {to_lang}. Only return the translation, nothing else: {input_text}"

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        return f"Translation error: {str(e)}"

# Example usage:
if __name__ == "__main__":
    # Example: Spanish to English
    spanish_text = "Hola mundo"
    translated = translate_text(spanish_text, target_lang="en", input_lang="es")
    print(f"Spanish: {spanish_text}")
    print(f"English: {translated}")

    # Example: Auto-detect to French
    english_text = "Hello world"
    translated = translate_text(english_text, target_lang="fr")
    print(f"\nAuto-detect: {english_text}")
    print(f"French: {translated}")




