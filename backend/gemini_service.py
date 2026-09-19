"""
Gemini Service Module for AI Quiz Generator.
Encapsulates all Google Gemini API interactions using the official `google-genai` SDK.
"""
import os
import json
import re
import time
from typing import Any, Dict, Optional, List
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.errors import APIError

load_dotenv()

class GeminiService:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY", "").strip()
        # Primary fast, free-tier model recommended by Google AI Studio
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
        self._client = None

    def _get_client(self) -> genai.Client:
        """Lazily initialize and return the official Gemini Client."""
        if not self.api_key or self.api_key == "your_gemini_api_key_here":
            # Refresh from environment in case .env was updated
            load_dotenv(override=True)
            self.api_key = os.getenv("GEMINI_API_KEY", "").strip()
        
        if not self.api_key or self.api_key == "your_gemini_api_key_here":
            raise ValueError(
                "GEMINI_API_KEY is not set or contains the default placeholder. "
                "Please configure your Gemini API key in the .env file."
            )
        
        if self._client is None:
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def is_configured(self) -> bool:
        """Returns True if a non-placeholder API key is set."""
        key = os.getenv("GEMINI_API_KEY", "").strip()
        return bool(key and key != "your_gemini_api_key_here")

    def clean_json_text(self, text: str) -> str:
        """Strips markdown fences and extracts valid JSON block."""
        text = text.strip()
        # Remove ```json and ``` fences if present
        pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
        return text

    def get_candidate_models(self) -> List[str]:
        """Returns ordered list of active models to try for high-demand resilience."""
        base_models = [
            "gemini-flash-latest",
            "gemini-flash-lite-latest",
            "gemini-2.5-flash",
            "gemini-2.5-pro"
        ]
        seen = set()
        return [m for m in base_models if not (m in seen or seen.add(m))]

    def generate_text(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        """Generates a plain-text response from Gemini with resilient model fallback."""
        client = self._get_client()
        last_err = None
        for model in self.get_candidate_models():
            try:
                config = types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.2
                )
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=config
                )
                return response.text or ""
            except APIError as e:
                last_err = e
                time.sleep(1.5)
                continue
            except Exception as e:
                last_err = e
                time.sleep(1.0)
                continue
        raise RuntimeError(f"All Gemini models exhausted. Last error: {str(last_err)}")

    def generate_json(self, prompt: str, system_instruction: Optional[str] = None) -> Any:
        """Generates structured JSON response with automatic markdown cleanup and resilient fallback."""
        client = self._get_client()
        last_err = None
        for model in self.get_candidate_models():
            try:
                config = types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                    temperature=0.2
                )
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=config
                )
                raw_text = response.text or "{}"
                cleaned = self.clean_json_text(raw_text)
                return json.loads(cleaned)
            except json.JSONDecodeError as jde:
                try:
                    json_match = re.search(r"(\[.*\]|\{.*\})", raw_text, re.DOTALL)
                    if json_match:
                        return json.loads(json_match.group(1))
                except Exception:
                    pass
                last_err = jde
                continue
            except APIError as e:
                last_err = e
                time.sleep(1.5)
                continue
            except Exception as e:
                last_err = e
                time.sleep(1.0)
                continue
        raise RuntimeError(f"All Gemini models exhausted. Last error: {str(last_err)}")

    def test_connection(self) -> Dict[str, Any]:
        """Performs a lightweight verification ping to Gemini."""
        if not self.is_configured():
            return {
                "success": False,
                "error": "GEMINI_API_KEY is not configured in .env."
            }
        try:
            prompt = "Return a JSON object with keys 'status' (value 'ok') and 'greeting' (short welcome phrase for an AI study tutor)."
            result = self.generate_json(prompt)
            return {
                "success": True,
                "model": self.model_name,
                "data": result
            }
        except Exception as e:
            return {
                "success": False,
                "model": self.model_name,
                "error": str(e)
            }

# Singleton instance for backend reuse
gemini_service = GeminiService()

