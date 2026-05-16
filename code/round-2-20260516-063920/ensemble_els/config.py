# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import json
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

try:
	from dotenv import load_dotenv
	load_dotenv()
except Exception:
	# 允许无 dotenv
	pass


def _split_csv(value: Optional[str]) -> List[str]:
	if not value:
		return []
	return [v.strip() for v in value.split(',') if v.strip()]


@dataclass
class ModelRateLimit:
	"""单个模型的速率限制配置"""
	rpm: int  # Requests Per Minute
	tpm: int  # Tokens Per Minute
	max_concurrent: int  # 该模型内部最大并发数，0表示不限制（全部并发）


@dataclass
class RuntimeConfig:
	# 路径
	excel_path: Optional[str]
	text_dir: Optional[str]
	output_dir: str

	# 模型与运行
	models: List[str]
	runs_per_model: int
	temperature: float
	request_timeout: int
	max_retries: int
	backoff_base: float
	log_level: str

	# 字段配置
	extract_fields_path: Optional[str]
	extract_fields_json: Optional[List[Dict[str, Any]]]

	# 模型密钥与名称
	moonshot_api_key: Optional[str]
	moonshot_model: str
	ark_api_key: Optional[str]
	deepseek_model: str
	doubao_model: str
	dashscope_api_key: Optional[str]
	qwen_model: str
	zhipu_api_key: Optional[str]
	glm_model: str
	google_api_key: Optional[str]
	gemini_model: str

	# vLLM 本地服务器配置
	vllm_base_url: str
	vllm_model: str

	# 速率限制配置（每个模型独立）
	rate_limits: Dict[str, ModelRateLimit]


def load_config(
	cli_overrides: Optional[Dict[str, Any]] = None,
) -> RuntimeConfig:
	cli_overrides = cli_overrides or {}

	def get(name: str, default: Optional[str] = None) -> Optional[str]:
		return str(cli_overrides.get(name, os.getenv(name, default))) if cli_overrides.get(name) is not None else os.getenv(name, default)

	# 路径（支持新旧两种配置方式）
	# 新配置：INDEX_PATH, TEXTS_PATH
	# 旧配置：EXCEL_PATH, TEXT_DIR（向后兼容）
	excel_path = get('INDEX_PATH') or get('EXCEL_PATH')
	text_dir = get('TEXTS_PATH') or get('TEXT_DIR')
	output_dir = get('OUTPUT_DIR', 'outputs')

	# 运行参数
	models = _split_csv(get('MODELS', 'KIMI,DEEPSEEK,GLM,QWEN,DOUBAO'))
	runs_per_model = int(get('RUNS_PER_MODEL', '10'))
	temperature = float(get('TEMPERATURE', '0'))
	request_timeout = int(get('REQUEST_TIMEOUT', '60'))
	max_retries = int(get('MAX_RETRIES', '12'))
	backoff_base = float(get('BACKOFF_BASE', '1.5'))
	log_level = str(get('LOG_LEVEL', 'INFO')).upper()

	# 字段定义
	extract_fields_path = get('EXTRACT_FIELDS_PATH')
	extract_fields_json_raw = get('EXTRACT_FIELDS_JSON')
	extract_fields_json = None
	if extract_fields_json_raw:
		try:
			extract_fields_json = json.loads(extract_fields_json_raw)
		except Exception:
			extract_fields_json = None

	# 模型密钥与模型名
	moonshot_api_key = get('MOONSHOT_API_KEY')
	moonshot_model = get('MOONSHOT_MODEL', 'kimi-k2-turbo-preview') or 'kimi-k2-turbo-preview'
	ark_api_key = get('ARK_API_KEY')
	deepseek_model = get('DEEPSEEK_MODEL', 'deepseek-r1-250528') or 'deepseek-r1-250528'
	doubao_model = get('DOUBAO_MODEL', 'doubao-seed-1-6-251015') or 'doubao-seed-1-6-251015'
	dashscope_api_key = get('DASHSCOPE_API_KEY')
	qwen_model = get('QWEN_MODEL', 'qwen-max') or 'qwen-max'
	zhipu_api_key = get('ZHIPUAI_API_KEY')
	glm_model = get('GLM_MODEL', 'glm-4.6') or 'glm-4.6'
	google_api_key = get('GOOGLE_API_KEY')
	gemini_model = get('GEMINI_MODEL', 'gemini-2.5-flash') or 'gemini-2.5-flash'

	# vLLM 本地服务器配置
	vllm_base_url = get('VLLM_BASE_URL', 'http://localhost:8000/v1') or 'http://localhost:8000/v1'
	vllm_model = get('VLLM_MODEL', 'qwen3-32b') or 'qwen3-32b'

	# 速率限制配置（默认值：0表示不限制）
	rate_limits = {}
	for model_key in ['KIMI', 'DEEPSEEK', 'DOUBAO', 'QWEN', 'GLM']:
		rpm = int(get(f'{model_key}_RPM', '0') or '0')
		tpm = int(get(f'{model_key}_TPM', '0') or '0')
		max_concurrent = int(get(f'{model_key}_MAX_CONCURRENT', '0') or '0')
		
		# 只要配置了任何一项（RPM/TPM/MAX_CONCURRENT），就创建配置对象
		if rpm > 0 or tpm > 0 or max_concurrent > 0:
			rate_limits[model_key] = ModelRateLimit(
				rpm=rpm if rpm > 0 else 999999,  # 不限制时设置极大值
				tpm=tpm if tpm > 0 else 999999,
				max_concurrent=max_concurrent if max_concurrent > 0 else 0,  # 0表示不限制
			)

	return RuntimeConfig(
		excel_path=excel_path,
		text_dir=text_dir,
		output_dir=output_dir,
		models=models,
		runs_per_model=runs_per_model,
		temperature=temperature,
		request_timeout=request_timeout,
		max_retries=max_retries,
		backoff_base=backoff_base,
		log_level=log_level,
		extract_fields_path=extract_fields_path,
		extract_fields_json=extract_fields_json,
		moonshot_api_key=moonshot_api_key,
		moonshot_model=moonshot_model,
		ark_api_key=ark_api_key,
		deepseek_model=deepseek_model,
		doubao_model=doubao_model,
		dashscope_api_key=dashscope_api_key,
		qwen_model=qwen_model,
		zhipu_api_key=zhipu_api_key,
		glm_model=glm_model,
		google_api_key=google_api_key,
		gemini_model=gemini_model,
		vllm_base_url=vllm_base_url,
		vllm_model=vllm_model,
		rate_limits=rate_limits,
	)

