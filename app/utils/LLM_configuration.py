# main.pyimport os
import google.generativeai as genai
from openai import OpenAI
from anthropic import Anthropic
from app.core.config import settings
from dotenv import load_dotenv
from app.utils.exceptions import LLMNotConfiguredError
import logging
import re, json

logger = logging.getLogger(__name__)


class LLMConfig:
    SUPPORTED_PROVIDERS = ['gemini', 'claude', 'openai']

    def __init__(self, model_provider: str = None, initial_history: list = None, model_name: str = None):
        self.model_provider = model_provider.lower()
        
        if self.model_provider not in self.SUPPORTED_PROVIDERS:
            logger.warning(f"Unsupported model provider: '{model_provider}'. Supported providers are: {self.SUPPORTED_PROVIDERS}")
            logger.warning("Defaulting to gemini 2.0 flash")

        # Use provided history or start with an empty list
        self.initial_history = initial_history if initial_history is not None else []
        self.chat_history = []
        
        # Initialize the appropriate client and model
        self._client = None
        if self.model_provider == 'gemini':
            api_key = settings.GEMINI_API_KEY
            if not api_key:
                raise LLMNotConfiguredError("GOOGLE_API_KEY environment variable not set.")
            genai.configure(api_key=api_key)
            self.model_name = model_name or 'gemini-2.0-flash'
            self._client = genai.GenerativeModel(self.model_name)
            # Start a chat session with the initial history
            self.chat_history = self._prepare_gemini_history()
            self._chat_session = self._client.start_chat(history=self.chat_history) # History here may be redundant


        elif self.model_provider == 'claude':
            api_key = settings.ANTHROPIC_API_KEY
            if not api_key:
                raise LLMNotConfiguredError("ANTHROPIC_API_KEY environment variable not set.")
            self.model_name = model_name or 'claude-3-haiku-20240307'
            self._client = Anthropic(api_key=api_key)
            self.chat_history = self._prepare_history()


        elif self.model_provider == 'openai':
            api_key = settings.OPENAI_API_KEY
            if not api_key:
                raise LLMNotConfiguredError("OPENAI_API_KEY environment variable not set.")
            self.model_name = model_name or 'gpt-4o'
            self._client = OpenAI(api_key=api_key)
            self.chat_history = self._prepare_history()
        
        # default
        else:
            api_key = settings.GEMINI_API_KEY
            if not api_key:
                raise ValueError("GOOGLE_API_KEY environment variable not set.")
            genai.configure(api_key=api_key)
            self.model_name = 'gemini-2.0-flash' # A good default
            self._client = genai.GenerativeModel(self.model_name)
            # Start a chat session with the initial history
            self._chat_session = self._client.start_chat(history=self._prepare_gemini_history())



    def _prepare_gemini_history(self):
        """Converts standard history to Gemini's format ('assistant' -> 'model')."""
        gemini_history = []
        for msg in self.initial_history:
            role = 'model' if msg.role == 'assistant' else msg.role
            gemini_history.append({'role': role, 'parts': [msg.content]})

        return gemini_history
    

    # For claude and openai
    def _prepare_history(self):
        history = []
        for msg in self.initial_history:
            history.append({'role': 'assistant', 'content': msg.content})
            
        return history
    


    def generate_response(self, prompt: str) -> str:

        # Add user's prompt to our internal history
        self.chat_history.append({"role": "user", "content": prompt})

        response_text = ""
        
        try:
            if self.model_provider == 'gemini':
                # For Gemini, we send only the new prompt to the ongoing session
                response = self._chat_session.send_message(prompt)
                response_text = response.text.strip()


            elif self.model_provider == 'claude':
                # Claude requires the full history each time
                response = self._client.messages.create(
                    model=self.model_name,
                    messages=self.chat_history
                )
                response_text = response.content[0].text

            elif self.model_provider == 'openai':
                # OpenAI also requires the full history
                response = self._client.chat.completions.create(
                    model=self.model_name,
                    messages=self.chat_history
                )
                response_text = response.choices[0].message.content
            
            return self.parse_json_response(response_text)
        
        except Exception as e:
            self.chat_history.pop()
            raise LLMNotConfiguredError(e)



    def parse_json_response(self, response_text):
        # If already a dict, return as is
        if isinstance(response_text, dict):
            return response_text
        # If not a string, try to convert to string
        if not isinstance(response_text, str):
            try:
                response_text = str(response_text)
            except Exception:
                raise ValueError("Response is neither string nor dict and cannot be converted to string.")
        text = response_text.strip()
        # Remove code fences if present
        if text.startswith('```'):
            text = re.sub(r'^```[a-zA-Z]*', '', text).strip()
            text = re.sub(r'```$', '', text).strip()
        # Try to parse as JSON
        try:
            return json.loads(text)
        except Exception:
            # Attempt to extract JSON object from within the response text
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                json_str = match.group(0)
                try:
                    return json.loads(json_str)
                except Exception as e:
                    raise ValueError(f"Extracted JSON but failed to parse: {e}")
            else:
                raise ValueError("No valid JSON found in response text")
