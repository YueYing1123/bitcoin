# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Optional
from zai import ZhipuAiClient
from ensemble_els.llm.base import LLMClientBase


class GLMClient(LLMClientBase):
	name = "GLM"

	def __init__(self, api_key: str, model: str, *, temperature: float, request_timeout: int, max_retries: int, backoff_base: float, rate_limiter=None) -> None:
		super().__init__(temperature=temperature, request_timeout=request_timeout, max_retries=max_retries, backoff_base=backoff_base, rate_limiter=rate_limiter)
		self.client = ZhipuAiClient(api_key=api_key)
		self.model = model

	def _invoke(self, prompt: str) -> str:
		resp = self.client.chat.completions.create(
			model=self.model,
			messages=[
				{"role": "system", "content": "你是一个有用的AI助手。严格输出JSON。"},
				{"role": "user", "content": prompt},
			],
			temperature=0,
		)
		return resp.choices[0].message.content or ""


