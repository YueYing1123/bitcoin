# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import logging
from typing import Optional

try:
	from aiolimiter import AsyncLimiter
except ImportError:
	AsyncLimiter = None  # type: ignore

logger = logging.getLogger(__name__)


class ModelRateLimiter:
	"""
	模型速率限制器，支持 RPM (Requests Per Minute) 和 TPM (Tokens Per Minute) 两种限制。
	
	使用 aiolimiter 库实现异步速率限制。
	"""
	
	def __init__(self, rpm: int, tpm: int):
		"""
		初始化速率限制器。
		
		Args:
			rpm: 每分钟最大请求数（Requests Per Minute）
			tpm: 每分钟最大令牌数（Tokens Per Minute）
		"""
		if AsyncLimiter is None:
			raise ImportError("需要安装 aiolimiter 库：pip install aiolimiter")
		
		self.rpm = rpm
		self.tpm = tpm
		
		# 创建两个独立的限制器
		# time_period=60 表示 60 秒的时间窗口
		self.rpm_limiter = AsyncLimiter(max_rate=rpm, time_period=60) if rpm > 0 else None
		self.tpm_limiter = AsyncLimiter(max_rate=tpm, time_period=60) if tpm > 0 else None
		
		logger.debug(f"创建速率限制器: RPM={rpm}, TPM={tpm}")
	
	async def acquire(self, estimated_tokens: int = 1):
		"""
		获取速率限制许可。
		
		Args:
			estimated_tokens: 预估的令牌数量，用于 TPM 限制。默认为 1。
		
		此方法会阻塞，直到可以获取到 RPM 和 TPM 的许可。
		"""
		# 先获取 RPM 许可（请求级别限制）
		if self.rpm_limiter:
			await self.rpm_limiter.acquire()
			logger.debug(f"获取 RPM 许可 (剩余容量: ~{self.rpm_limiter.max_rate - self.rpm_limiter._level:.0f})")
		
		# 再获取 TPM 许可（令牌级别限制）
		if self.tpm_limiter and estimated_tokens > 0:
			# aiolimiter 支持一次获取多个令牌
			await self.tpm_limiter.acquire(estimated_tokens)
			logger.debug(f"获取 TPM 许可 (消耗 {estimated_tokens} tokens)")
	
	async def __aenter__(self):
		"""支持异步上下文管理器"""
		await self.acquire()
		return self
	
	async def __aexit__(self, exc_type, exc_val, exc_tb):
		"""异步上下文管理器退出"""
		return False


class NoOpRateLimiter:
	"""
	空操作速率限制器，用于在不需要限制时提供统一接口。
	"""
	
	def __init__(self):
		logger.debug("创建无限制速率限制器（NoOp）")
	
	async def acquire(self, estimated_tokens: int = 1):
		"""不执行任何限制，立即返回"""
		pass
	
	async def __aenter__(self):
		return self
	
	async def __aexit__(self, exc_type, exc_val, exc_tb):
		return False

