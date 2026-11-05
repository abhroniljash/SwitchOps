"""
LLM Client: Provides direct integration with real LLM APIs (Google Gemini, OpenAI, Claude).
Enables the Triage and Remediation agents to generate dynamic, evidence-backed
analyses and code patches using state-of-the-art foundation models.
"""

import json
import logging
import os
from typing import Dict, Any, Optional
import requests

logger = logging.getLogger("switchops.llm_client")


class LLMClient:
    """Multi-provider client supporting Gemini, OpenAI, and Claude with graceful fallbacks."""

    def __init__(
        self,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout_seconds: int = 20
    ):
        self.provider = (provider or os.getenv("LLM_PROVIDER", "gemini")).lower()
        self.timeout = timeout_seconds

        # Resolve credentials based on provider
        if self.provider == "gemini":
            self.api_key = api_key or os.getenv("GEMINI_API_KEY")
            self.model_name = model_name or "gemini-2.5-flash"
        elif self.provider == "openai":
            self.api_key = api_key or os.getenv("OPENAI_API_KEY")
            self.model_name = model_name or "gpt-4o-mini"
        elif self.provider in ["anthropic", "claude"]:
            self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
            self.model_name = model_name or "claude-3-5-sonnet-20241022"
        else:
            self.api_key = api_key
            self.model_name = model_name or "mock"

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    def generate(self, prompt: str, system_instruction: Optional[str] = None) -> Dict[str, Any]:
        """
        Sends prompt to the configured LLM provider.
        Returns a dict with: {'text': str, 'provider': str, 'model': str, 'live': bool}
        """
        if not self.is_configured:
            logger.info(f"[LLMClient] No API key detected for {self.provider}; using deterministic SRE engine.")
            return {
                "text": None,
                "provider": "deterministic-fallback",
                "model": "offline-sre-engine",
                "live": False,
                "reason": f"No API key provided in {self.provider.upper()}_API_KEY",
            }

        try:
            if self.provider == "gemini":
                return self._call_gemini(prompt, system_instruction)
            elif self.provider == "openai":
                return self._call_openai(prompt, system_instruction)
            elif self.provider in ["anthropic", "claude"]:
                return self._call_anthropic(prompt, system_instruction)
            else:
                return {
                    "text": None,
                    "provider": self.provider,
                    "model": self.model_name,
                    "live": False,
                    "reason": f"Unsupported provider: {self.provider}",
                }
        except Exception as e:
            logger.warning(f"[LLMClient] Error calling {self.provider} API: {e}; falling back.")
            return {
                "text": None,
                "provider": self.provider,
                "model": self.model_name,
                "live": False,
                "error": str(e),
            }

    def _call_gemini(self, prompt: str, system_instruction: Optional[str] = None) -> Dict[str, Any]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
        
        contents = []
        if system_instruction:
            contents.append({"role": "user", "parts": [{"text": f"System context:\n{system_instruction}"}]})
            contents.append({"role": "model", "parts": [{"text": "Understood. I will act strictly according to these instructions."}]})
        
        contents.append({"role": "user", "parts": [{"text": prompt}]})

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 2048,
            }
        }

        resp = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        
        text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        return {
            "text": text,
            "provider": "Google Gemini",
            "model": self.model_name,
            "live": True,
        }

    def _call_openai(self, prompt: str, system_instruction: Optional[str] = None) -> Dict[str, Any]:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": 0.2,
        }

        resp = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()

        text = data["choices"][0]["message"]["content"].strip()
        return {
            "text": text,
            "provider": "OpenAI",
            "model": self.model_name,
            "live": True,
        }

    def _call_anthropic(self, prompt: str, system_instruction: Optional[str] = None) -> Dict[str, Any]:
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model_name,
            "max_tokens": 2048,
            "temperature": 0.2,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_instruction:
            payload["system"] = system_instruction

        resp = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()

        text = data["content"][0]["text"].strip()
        return {
            "text": text,
            "provider": "Anthropic Claude",
            "model": self.model_name,
            "live": True,
        }
