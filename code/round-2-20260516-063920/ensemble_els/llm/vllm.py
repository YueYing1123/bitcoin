# -*- coding: utf-8 -*-
"""
vLLM 本地服务器客户端

用于连接通过 vLLM 启动的 OpenAI 兼容 API 服务器。

使用示例：
    python -m vllm.entrypoints.openai.api_server \
        --model /path/to/model \
        --served-model-name model-name \
        --port 8000 \
        --gpu-memory-utilization 0.85
"""
from __future__ import annotations

from openai import OpenAI
from ensemble_els.llm.base import LLMClientBase


class VLLMClient(LLMClientBase):
    """
    连接本地 vLLM OpenAI 兼容服务器的客户端。
    
    Args:
        base_url: vLLM 服务器地址，如 "http://localhost:8000/v1"
        model: 服务器上配置的 served-model-name
        temperature: 温度参数
        request_timeout: 请求超时时间（秒）
        max_retries: 最大重试次数
        backoff_base: 重试退避基数
        rate_limiter: 速率限制器（可选）
    """
    name = "VLLM"

    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        temperature: float = 0,
        request_timeout: int = 120,
        max_retries: int = 12,
        backoff_base: float = 1.5,
        rate_limiter=None,
    ) -> None:
        super().__init__(
            temperature=temperature,
            request_timeout=request_timeout,
            max_retries=max_retries,
            backoff_base=backoff_base,
            rate_limiter=rate_limiter,
        )
        # vLLM OpenAI 兼容服务器不需要 API key，但 OpenAI SDK 要求提供
        self.client = OpenAI(
            api_key="not-needed",  # vLLM 本地服务器不验证 API key
            base_url=base_url,
            timeout=request_timeout,
        )
        self.model = model

    def _invoke(self, prompt: str) -> str:
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant. 严格输出JSON。"},
                {"role": "user", "content": prompt},
            ],
            temperature=self.temperature,
        )
        return resp.choices[0].message.content or ""

