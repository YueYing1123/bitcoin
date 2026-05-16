# -*- coding: utf-8 -*-
from __future__ import annotations
import json
import logging
import asyncio
from typing import Any, Dict, List, Optional
from jinja2 import Environment, FileSystemLoader, select_autoescape
import os

from ensemble_els.utils.retry import retry


logger = logging.getLogger(__name__)


def render_prompt(document_id: str, meta: Dict[str, Any], document_text: str, fields: List[Dict[str, Any]]) -> str:
	template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'prompts')
	env = Environment(
		loader=FileSystemLoader(template_dir),
		autoescape=select_autoescape(disabled_extensions=(".jinja2",)),
	)
	tpl = env.get_template('extract_cn.jinja2')
	meta_map = {
		'title': meta.get('文书标题'),
		'case_reason': meta.get('案由/罪名'),
		'case_number': meta.get('案号'),
		'judgment_date': meta.get('审结时间'),
		'court_name': meta.get('审理法院'),
		'court_level': meta.get('法院级别'),
		'procedure_stage': meta.get('审理程序'),
	}
	return tpl.render(document_id=document_id, meta=meta_map, document_text=document_text, fields=fields)


def safe_json_parse(content: str) -> Any:
	# 只取第一个大括号到最后一个大括号之间的 JSON
	start = content.find('{')
	end = content.rfind('}')
	if start != -1 and end != -1 and end > start:
		try:
			return json.loads(content[start:end+1])
		except Exception:
			pass
	# 直接尝试整体解析
	return json.loads(content)


class LLMClientBase:
	name: str = "BASE"

	def __init__(self, *, temperature: float, request_timeout: int, max_retries: int, backoff_base: float, rate_limiter: Optional[Any] = None) -> None:
		self.temperature = temperature
		self.request_timeout = request_timeout
		self.max_retries = max_retries
		self.backoff_base = backoff_base
		self.rate_limiter = rate_limiter

	def _invoke(self, prompt: str) -> str:
		raise NotImplementedError

	def generate(self, *, document_id: str, meta: Dict[str, Any], document_text: str, fields: List[Dict[str, Any]]) -> Dict[str, Any]:
		prompt = render_prompt(document_id, meta, document_text, fields)
		attempt = 0
		while True:
			try:
				raw = self._invoke(prompt)
				return safe_json_parse(raw)
			except Exception as e:
				attempt += 1
				logger.error(f"{self.name} 调用/解析失败，第{attempt}次：{e}")
				if attempt >= self.max_retries:
					raise
				import time
				backoff = min(self.backoff_base ** (attempt - 1), 30)
				time.sleep(backoff)

	async def generate_async(self, *, document_id: str, meta: Dict[str, Any], document_text: str, fields: List[Dict[str, Any]], estimated_tokens: int = 2000) -> Dict[str, Any]:
		"""
		异步生成方法，支持速率限制。
		
		Args:
			document_id: 文档ID
			meta: 元数据
			document_text: 文档文本
			fields: 字段定义
			estimated_tokens: 预估令牌数（用于TPM限制），默认2000
		
		Returns:
			生成的结果字典
		"""
		# 如果配置了速率限制器，先获取许可
		if self.rate_limiter:
			await self.rate_limiter.acquire(estimated_tokens)
			logger.debug(f"{self.name} 获取速率限制许可成功 (预估 {estimated_tokens} tokens)")
		
		# 在线程池中执行同步的 generate 方法
		# 这样可以避免阻塞事件循环
		loop = asyncio.get_event_loop()
		result = await loop.run_in_executor(
			None,
			lambda: self.generate(
				document_id=document_id,
				meta=meta,
				document_text=document_text,
				fields=fields
			)
		)
		return result

