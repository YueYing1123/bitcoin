# -*- coding: utf-8 -*-
from __future__ import annotations
import logging
from typing import Any, Dict, List
from google import genai
from ensemble_els.llm.base import LLMClientBase


logger = logging.getLogger(__name__)


class GeminiClient(LLMClientBase):
	name = "GEMINI"

	def __init__(self, api_key: str, model: str, *, temperature: float, request_timeout: int, max_retries: int, backoff_base: float, rate_limiter=None) -> None:
		super().__init__(temperature=temperature, request_timeout=request_timeout, max_retries=max_retries, backoff_base=backoff_base, rate_limiter=rate_limiter)
		self.client = genai.Client(api_key=api_key)
		self.model = model

	def _invoke(self, prompt: str) -> str:
		response = self.client.models.generate_content(
			model=self.model,
			contents=prompt,
		)
		return response.text or ""

