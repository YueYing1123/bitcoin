# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import json
import re
import yaml
import argparse
import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime

import random
import shutil

from ensemble_els.config import load_config, RuntimeConfig
from ensemble_els.utils.logging import setup_logging
from ensemble_els.utils.progress import iter_with_progress
from ensemble_els.io.excel_reader import read_excel_records, get_row_by_index
from ensemble_els.io.text_loader import load_document_text
from ensemble_els.llm.kimi import KimiClient
from ensemble_els.llm.deepseek import DeepseekClient
from ensemble_els.llm.doubao import DoubaoClient
from ensemble_els.llm.qwen import QwenClient
from ensemble_els.llm.glm import GLMClient
from ensemble_els.llm.gemini import GeminiClient
from ensemble_els.llm.vllm import VLLMClient
from ensemble_els.ensemble.model_level_vote import model_level_vote
from ensemble_els.ensemble.cross_model_vote import cross_model_vote
from ensemble_els.utils.rate_limiter import ModelRateLimiter, NoOpRateLimiter


RUN_FILE_PATTERN = re.compile(r'^run_(\d+)\.json$')


def load_fields(cfg: RuntimeConfig) -> List[Dict[str, Any]]:
	if cfg.extract_fields_path and os.path.isfile(cfg.extract_fields_path):
		with open(cfg.extract_fields_path, 'r', encoding='utf-8') as f:
			obj = yaml.safe_load(f)
		return obj.get('fields', [])
	if cfg.extract_fields_json:
		return cfg.extract_fields_json
	# fallback default
	default_path = os.path.join('docs', 'fields.yaml')
	if os.path.isfile(default_path):
		with open(default_path, 'r', encoding='utf-8') as f:
			obj = yaml.safe_load(f)
		return obj.get('fields', [])
	return []


def ensure_dirs(base_output: str, doc_id: str, models: List[str]) -> Dict[str, str]:
	paths = {}
	raw_root = os.path.join(base_output, 'raw', doc_id)
	os.makedirs(raw_root, exist_ok=True)
	for m in models:
		p = os.path.join(raw_root, m)
		os.makedirs(p, exist_ok=True)
		paths[m] = p
	consensus_dir = os.path.join(base_output, 'consensus', doc_id)
	final_dir = os.path.join(base_output, 'final')
	os.makedirs(consensus_dir, exist_ok=True)
	os.makedirs(final_dir, exist_ok=True)
	paths['consensus'] = consensus_dir
	paths['final'] = final_dir
	return paths


def make_clients(cfg: RuntimeConfig, models: List[str]):
	"""
	创建模型客户端，并为每个客户端配置速率限制器。
	"""
	logger = logging.getLogger('make_clients')
	clients = {}
	
	for m in models:
		mm = m.strip().upper()
		
		# 为该模型创建速率限制器
		rate_limiter = None
		if mm in cfg.rate_limits:
			limit_cfg = cfg.rate_limits[mm]
			try:
				rate_limiter = ModelRateLimiter(rpm=limit_cfg.rpm, tpm=limit_cfg.tpm)
				logger.info(f"模型 {mm} 配置速率限制: RPM={limit_cfg.rpm}, TPM={limit_cfg.tpm}")
			except ImportError as e:
				logger.warning(f"无法为模型 {mm} 创建速率限制器: {e}，将不限制速率")
				rate_limiter = NoOpRateLimiter()
		else:
			logger.info(f"模型 {mm} 未配置速率限制，将不限制速率")
			rate_limiter = NoOpRateLimiter()
		
		# 创建客户端并传入速率限制器
		if mm == 'KIMI' and cfg.moonshot_api_key:
			clients[mm] = KimiClient(
				cfg.moonshot_api_key,
				cfg.moonshot_model,
				temperature=0,
				request_timeout=cfg.request_timeout,
				max_retries=cfg.max_retries,
				backoff_base=cfg.backoff_base,
				rate_limiter=rate_limiter,
			)
		elif mm == 'DEEPSEEK' and cfg.ark_api_key:
			clients[mm] = DeepseekClient(
				cfg.ark_api_key,
				cfg.deepseek_model,
				temperature=0,
				request_timeout=cfg.request_timeout,
				max_retries=cfg.max_retries,
				backoff_base=cfg.backoff_base,
				rate_limiter=rate_limiter,
			)
		elif mm == 'DOUBAO' and cfg.ark_api_key:
			clients[mm] = DoubaoClient(
				cfg.ark_api_key,
				cfg.doubao_model,
				temperature=0,
				request_timeout=cfg.request_timeout,
				max_retries=cfg.max_retries,
				backoff_base=cfg.backoff_base,
				rate_limiter=rate_limiter,
			)
		elif mm == 'QWEN' and cfg.dashscope_api_key:
			clients[mm] = QwenClient(
				cfg.dashscope_api_key,
				cfg.qwen_model,
				temperature=0,
				request_timeout=cfg.request_timeout,
				max_retries=cfg.max_retries,
				backoff_base=cfg.backoff_base,
				rate_limiter=rate_limiter,
			)
		elif mm == 'GLM' and cfg.zhipu_api_key:
			clients[mm] = GLMClient(
				cfg.zhipu_api_key,
				cfg.glm_model,
				temperature=0,
				request_timeout=cfg.request_timeout,
				max_retries=cfg.max_retries,
				backoff_base=cfg.backoff_base,
				rate_limiter=rate_limiter,
			)
	
	return clients


async def collect_for_doc_async(cfg: RuntimeConfig, record: Dict[str, Any], models: List[str], runs_per_model: int, fields: List[Dict[str, Any]]):
	"""
	异步并发收集单个文档的结果。
	- 模型之间并发执行
	- 每个模型内部的多次运行也并发执行
	"""
	logger = logging.getLogger('collect_async')
	document_id = str(record['可唯一识别id'])
	paths = ensure_dirs(cfg.output_dir, document_id, models)
	text = load_document_text(cfg.text_dir, document_id)
	clients = make_clients(cfg, models)
	
	async def run_single_model_all_runs(model_name: str, client, runs: int):
		"""
		单个模型的所有运行次数并发执行，支持并发数控制。
		"""
		# 获取该模型的并发限制
		max_concurrent = 0  # 默认不限制
		if model_name in cfg.rate_limits:
			max_concurrent = cfg.rate_limits[model_name].max_concurrent
		
		# 如果配置了并发限制，创建 Semaphore
		semaphore = asyncio.Semaphore(max_concurrent) if max_concurrent > 0 else None
		
		if max_concurrent > 0:
			logger.info(f"[{document_id}] 模型 {model_name} 配置最大并发数: {max_concurrent}")
		else:
			logger.info(f"[{document_id}] 模型 {model_name} 无并发限制（全部并发）")
		
		async def run_once(run_index: int):
			# 如果有并发限制，先获取许可
			if semaphore:
				async with semaphore:
					return await _do_run(run_index)
			else:
				return await _do_run(run_index)
		
		async def _do_run(run_index: int):
			try:
				logger.info(f"[{document_id}] 模型 {model_name} 第 {run_index} 次运行开始")
				res = await client.generate_async(
					document_id=document_id,
					meta=record,
					document_text=text,
					fields=fields,
					estimated_tokens=2000  # 预估token数，可根据实际情况调整
				)
				
				# 保存结果
				out_path = os.path.join(paths[model_name], f"run_{run_index}.json")
				ts = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
				out_path_ts = os.path.join(paths[model_name], f"run_{run_index}_{ts}.json")
				
				with open(out_path, 'w', encoding='utf-8') as f:
					json.dump(res, f, ensure_ascii=False, indent=2)
				with open(out_path_ts, 'w', encoding='utf-8') as f:
					json.dump(res, f, ensure_ascii=False, indent=2)
				
				logger.info(f"[{document_id}] 模型 {model_name} 第 {run_index} 次运行完成")
				return res
			except Exception as e:
				logger.error(f"[{document_id}] 模型 {model_name} 第 {run_index} 次运行失败: {e}", exc_info=True)
				return None
		
		# 该模型的所有运行次数并发执行（受 semaphore 控制）
		tasks = [run_once(k) for k in range(1, runs + 1)]
		results = await asyncio.gather(*tasks, return_exceptions=True)
		return results
	
	# 所有模型并发执行
	logger.info(f"[{document_id}] 开始并发处理 {len(clients)} 个模型，每个模型 {runs_per_model} 次运行")
	model_tasks = [
		run_single_model_all_runs(model_name, client, runs_per_model)
		for model_name, client in clients.items()
	]
	
	all_results = await asyncio.gather(*model_tasks, return_exceptions=True)
	logger.info(f"[{document_id}] 所有模型处理完成")
	return all_results


def collect_for_doc(cfg: RuntimeConfig, record: Dict[str, Any], models: List[str], runs_per_model: int, fields: List[Dict[str, Any]]):
	"""
	同步版本的collect_for_doc，保留用于向后兼容。
	"""
	logger = logging.getLogger('collect')
	document_id = str(record['可唯一识别id'])
	paths = ensure_dirs(cfg.output_dir, document_id, models)
	text = load_document_text(cfg.text_dir, document_id)
	clients = make_clients(cfg, models)
	for m, client in clients.items():
		for k in range(1, runs_per_model + 1):
			try:
				res = client.generate(document_id=document_id, meta=record, document_text=text, fields=fields)
				out_path = os.path.join(paths[m], f"run_{k}.json")
				ts = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
				out_path_ts = os.path.join(paths[m], f"run_{k}_{ts}.json")
				with open(out_path, 'w', encoding='utf-8') as f:
					json.dump(res, f, ensure_ascii=False, indent=2)
				with open(out_path_ts, 'w', encoding='utf-8') as f:
					json.dump(res, f, ensure_ascii=False, indent=2)
			except Exception as e:
				logger.error(f"模型 {m} 第{k}次失败: {e}")


def cmd_collect(args):
	"""
	collect命令入口，支持异步并发。
	"""
	cfg = load_config({
		'EXCEL_PATH': args.excel,
		'TEXT_DIR': args.text_dir,
		'OUTPUT_DIR': args.output,
		'MODELS': ','.join(args.models) if args.models else None,
		'RUNS_PER_MODEL': str(args.runs_per_model) if args.runs_per_model else None,
	})
	setup_logging(cfg.log_level)
	logger = logging.getLogger('cmd_collect')
	fields = load_fields(cfg)
	recs = read_excel_records(cfg.excel_path, limit=args.limit or 0)
	
	# 检查是否可以使用异步并发
	use_async = len(cfg.rate_limits) > 0 or True  # 默认使用异步
	
	if use_async:
		logger.info("使用异步并发模式处理文档")
		# 使用异步模式
		for rec in iter_with_progress(recs, desc='collect'):
			asyncio.run(collect_for_doc_async(
				cfg,
				rec,
				[m.strip().upper() for m in (args.models or cfg.models)],
				args.runs_per_model or cfg.runs_per_model,
				fields,
			))
	else:
		logger.info("使用同步模式处理文档")
		# 使用同步模式（向后兼容）
		for rec in iter_with_progress(recs, desc='collect'):
			collect_for_doc(
				cfg,
				rec,
				[m.strip().upper() for m in (args.models or cfg.models)],
				args.runs_per_model or cfg.runs_per_model,
				fields,
			)


def read_json(path: str) -> Any:
	with open(path, 'r', encoding='utf-8') as f:
		return json.load(f)


def cmd_vote(args):
	cfg = load_config({'OUTPUT_DIR': args.output})
	setup_logging(cfg.log_level)
	logger = logging.getLogger('vote')
	doc_id = args.document_id
	base = os.path.join(cfg.output_dir, 'raw', doc_id)
	if not os.path.isdir(base):
		raise FileNotFoundError(f"未找到原始结果目录: {base}")
	# gather models and runs
	model_votes: Dict[str, Dict[str, Dict[str, Any]]] = {}
	# 确定 targets 列表
	fields = load_fields(cfg)
	targets = [f['target'] for f in fields if 'target' in f]
	for m in os.listdir(base):
		m_dir = os.path.join(base, m)
		if not os.path.isdir(m_dir):
			continue
		run_files = [
			fn for fn in os.listdir(m_dir)
			if RUN_FILE_PATTERN.match(fn)
		]
		if not run_files:
			logger.warning(f"模型 {m} 未找到 run_k.json 快照，已跳过")
			continue
		run_files.sort(key=lambda fn: int(RUN_FILE_PATTERN.match(fn).group(1)))
		runs = [read_json(os.path.join(m_dir, fn)) for fn in run_files]
		mv = model_level_vote(runs, targets=targets, threshold=args.model_level_threshold)
		model_votes[m] = mv

	finals, metrics = cross_model_vote(model_votes)

	consensus_dir = os.path.join(cfg.output_dir, 'consensus', doc_id)
	final_dir = os.path.join(cfg.output_dir, 'final')
	os.makedirs(consensus_dir, exist_ok=True)
	os.makedirs(final_dir, exist_ok=True)
	ts = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
	# 最新文件
	with open(os.path.join(consensus_dir, 'model_level.json'), 'w', encoding='utf-8') as f:
		json.dump(model_votes, f, ensure_ascii=False, indent=2)
	with open(os.path.join(final_dir, f'{doc_id}.json'), 'w', encoding='utf-8') as f:
		json.dump({"final_fields": finals, "metrics": metrics}, f, ensure_ascii=False, indent=2)
	# 归档带时间戳
	with open(os.path.join(consensus_dir, f'model_level_{ts}.json'), 'w', encoding='utf-8') as f:
		json.dump(model_votes, f, ensure_ascii=False, indent=2)
	with open(os.path.join(final_dir, f'{doc_id}_{ts}.json'), 'w', encoding='utf-8') as f:
		json.dump({"final_fields": finals, "metrics": metrics}, f, ensure_ascii=False, indent=2)


def cmd_vote_batch(args):
	cfg = load_config({'OUTPUT_DIR': args.output})
	setup_logging(cfg.log_level)
	raw_root = os.path.join(cfg.output_dir, 'raw')
	if not os.path.isdir(raw_root):
		raise FileNotFoundError(f"未找到原始结果根目录: {raw_root}")
	doc_ids = [d for d in os.listdir(raw_root) if os.path.isdir(os.path.join(raw_root, d))]
	for doc_id in iter_with_progress(doc_ids, desc='vote'):
		cmd_vote(argparse.Namespace(document_id=doc_id, output=cfg.output_dir, model_level_threshold=args.model_level_threshold))


def cmd_validate_one(args):
	"""
	validate-one命令入口，支持异步并发。
	"""
	cfg = load_config({
		'EXCEL_PATH': args.excel,
		'TEXT_DIR': args.text_dir,
		'OUTPUT_DIR': args.output,
		'MODELS': ','.join(args.models) if args.models else None,
		'RUNS_PER_MODEL': '1',
	})
	setup_logging(cfg.log_level)
	fields = load_fields(cfg)
	if args.document_id:
		record = {
			"文书标题": None,
			"案由/罪名": None,
			"案号": None,
			"审结时间": None,
			"审理法院": None,
			"法院级别": None,
			"审理程序": None,
			"可唯一识别id": args.document_id,
		}
	else:
		record = get_row_by_index(cfg.excel_path, args.row_index or 0)
	
	# 使用异步版本
	asyncio.run(collect_for_doc_async(
		cfg,
		record,
		[m.strip().upper() for m in (args.models or cfg.models)],
		1,
		fields,
	))
	
	cmd_vote(argparse.Namespace(document_id=str(record['可唯一识别id']), output=cfg.output_dir, model_level_threshold=0.7))


def cmd_test_gemini(args):
	"""
	test-gemini命令入口：随机抽样数据，调用Gemini API，输出到test文件夹。
	"""
	cfg = load_config({
		'EXCEL_PATH': args.excel,
		'TEXT_DIR': args.text_dir,
		'OUTPUT_DIR': args.output,
	})
	setup_logging(cfg.log_level)
	logger = logging.getLogger('test_gemini')
	
	# 检查 API 密钥
	if not cfg.google_api_key:
		raise ValueError("未配置 GOOGLE_API_KEY，请在 .env 文件中添加")
	
	# 读取所有记录
	all_records = list(read_excel_records(cfg.excel_path, limit=0))
	logger.info(f"共读取 {len(all_records)} 条记录")
	
	# 随机抽样
	sample_count = min(args.sample, len(all_records))
	sampled_records = random.sample(all_records, sample_count)
	logger.info(f"随机抽取 {sample_count} 条记录")
	
	# 创建输出目录：outputs/test/<timestamp>/
	timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
	test_output_dir = os.path.join(cfg.output_dir, 'test', timestamp)
	os.makedirs(test_output_dir, exist_ok=True)
	logger.info(f"输出目录: {test_output_dir}")
	
	# 加载字段配置
	fields = load_fields(cfg)
	
	# 创建 Gemini 客户端
	gemini_client = GeminiClient(
		api_key=cfg.google_api_key,
		model=cfg.gemini_model,
		temperature=cfg.temperature,
		request_timeout=cfg.request_timeout,
		max_retries=cfg.max_retries,
		backoff_base=cfg.backoff_base,
	)
	
	# 处理记录摘要
	md_lines = [
		f"# Gemini 测试抽样记录",
		f"",
		f"- **抽样时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
		f"- **抽样数量**: {sample_count}",
		f"- **模型**: {cfg.gemini_model}",
		f"",
		f"## 抽样记录列表",
		f"",
		f"| 序号 | 文档ID | 案号 | 处理状态 |",
		f"|------|--------|------|----------|",
	]
	
	# 处理每条记录
	for idx, record in enumerate(iter_with_progress(sampled_records, desc='test-gemini'), 1):
		doc_id = str(record['可唯一识别id'])
		case_number = record.get('案号', '未知')
		
		try:
			# 加载原始文档
			text = load_document_text(cfg.text_dir, doc_id)
			
			# 复制原始 txt 文件
			original_txt_path = os.path.join(test_output_dir, f"{doc_id}_original.txt")
			with open(original_txt_path, 'w', encoding='utf-8') as f:
				f.write(text)
			
			# 调用 Gemini API
			result = gemini_client.generate(
				document_id=doc_id,
				meta=record,
				document_text=text,
				fields=fields
			)
			
			# 保存 Gemini 输出
			gemini_output_path = os.path.join(test_output_dir, f"{doc_id}_gemini.json")
			with open(gemini_output_path, 'w', encoding='utf-8') as f:
				json.dump(result, f, ensure_ascii=False, indent=2)
			
			md_lines.append(f"| {idx} | `{doc_id}` | {case_number} | ✅ 成功 |")
			logger.info(f"[{idx}/{sample_count}] 文档 {doc_id} 处理成功")
			
		except Exception as e:
			md_lines.append(f"| {idx} | `{doc_id}` | {case_number} | ❌ 失败: {str(e)[:30]} |")
			logger.error(f"[{idx}/{sample_count}] 文档 {doc_id} 处理失败: {e}")
	
	# 生成摘要 Markdown 文件
	md_lines.extend([
		f"",
		f"---",
		f"",
		f"## 详细记录",
		f"",
	])
	
	for idx, record in enumerate(sampled_records, 1):
		doc_id = str(record['可唯一识别id'])
		md_lines.extend([
			f"### {idx}. {doc_id}",
			f"",
			f"- **案号**: {record.get('案号', '未知')}",
			f"- **文书标题**: {record.get('文书标题', '未知')}",
			f"- **案由/罪名**: {record.get('案由/罪名', '未知')}",
			f"- **审理法院**: {record.get('审理法院', '未知')}",
			f"- **审结时间**: {record.get('审结时间', '未知')}",
			f"",
		])
	
	md_path = os.path.join(test_output_dir, 'sample_records.md')
	with open(md_path, 'w', encoding='utf-8') as f:
		f.write('\n'.join(md_lines))
	
	logger.info(f"抽样记录摘要已保存至: {md_path}")
	logger.info(f"测试完成！输出目录: {test_output_dir}")


def cmd_local_collect(args):
	"""
	local-collect 命令入口：连接本地 vLLM 服务器，对指定文档运行 N 次问答。
	
	工作流程：
	1. 用户启动 vLLM 服务器（如 qwen3-32b）
	2. 运行此命令收集该模型的结果
	3. 用户切换模型后再次运行
	4. 最后使用 local-vote 命令汇总投票
	"""
	cfg = load_config({
		'EXCEL_PATH': args.excel,
		'TEXT_DIR': args.text_dir,
		'OUTPUT_DIR': args.output,
		'VLLM_BASE_URL': args.base_url,
		'VLLM_MODEL': args.model_name,
		'RUNS_PER_MODEL': str(args.runs) if args.runs else None,
	})
	setup_logging(cfg.log_level)
	logger = logging.getLogger('local_collect')
	
	# 创建 vLLM 客户端
	vllm_client = VLLMClient(
		base_url=cfg.vllm_base_url,
		model=cfg.vllm_model,
		temperature=cfg.temperature,
		request_timeout=cfg.request_timeout,
		max_retries=cfg.max_retries,
		backoff_base=cfg.backoff_base,
	)
	
	# 加载字段配置
	fields = load_fields(cfg)
	
	# 确定要处理的文档
	if args.document_id:
		# 直接使用指定的文档 ID
		record = {
			"文书标题": None,
			"案由/罪名": None,
			"案号": None,
			"审结时间": None,
			"审理法院": None,
			"法院级别": None,
			"审理程序": None,
			"可唯一识别id": args.document_id,
		}
		records = [record]
	else:
		# 从 Excel 读取
		records = list(read_excel_records(cfg.excel_path, limit=args.limit or 0))
	
	logger.info(f"连接 vLLM 服务器: {cfg.vllm_base_url}")
	logger.info(f"模型名称: {cfg.vllm_model}")
	logger.info(f"待处理文档数: {len(records)}")
	logger.info(f"每个文档运行次数: {args.runs or cfg.runs_per_model}")
	
	runs = args.runs or cfg.runs_per_model
	model_name = cfg.vllm_model.upper().replace('-', '_')  # 规范化模型名称作为目录名
	
	for record in iter_with_progress(records, desc='local-collect'):
		doc_id = str(record['可唯一识别id'])
		
		# 创建输出目录
		raw_dir = os.path.join(cfg.output_dir, 'raw', doc_id, model_name)
		os.makedirs(raw_dir, exist_ok=True)
		
		# 加载文档文本
		try:
			text = load_document_text(cfg.text_dir, doc_id)
		except Exception as e:
			logger.error(f"文档 {doc_id} 加载失败: {e}")
			continue
		
		# 运行 N 次
		for k in range(1, runs + 1):
			try:
				logger.info(f"[{doc_id}] 第 {k}/{runs} 次运行")
				result = vllm_client.generate(
					document_id=doc_id,
					meta=record,
					document_text=text,
					fields=fields,
				)
				
				# 保存结果
				out_path = os.path.join(raw_dir, f"run_{k}.json")
				ts = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
				out_path_ts = os.path.join(raw_dir, f"run_{k}_{ts}.json")
				
				with open(out_path, 'w', encoding='utf-8') as f:
					json.dump(result, f, ensure_ascii=False, indent=2)
				with open(out_path_ts, 'w', encoding='utf-8') as f:
					json.dump(result, f, ensure_ascii=False, indent=2)
				
				logger.info(f"[{doc_id}] 第 {k}/{runs} 次运行完成")
			except Exception as e:
				logger.error(f"[{doc_id}] 第 {k}/{runs} 次运行失败: {e}")
	
	logger.info(f"收集完成！结果保存在: {cfg.output_dir}/raw/")
	logger.info(f"模型结果目录: {model_name}")


def cmd_local_vote(args):
	"""
	local-vote 命令入口：对本地收集的多个模型结果进行投票。
	
	此命令会读取 outputs/raw/{document_id}/ 下所有模型的结果，
	进行模型内投票和模型间投票，输出最终结果。
	"""
	cfg = load_config({'OUTPUT_DIR': args.output})
	setup_logging(cfg.log_level)
	logger = logging.getLogger('local_vote')
	
	raw_root = os.path.join(cfg.output_dir, 'raw')
	if not os.path.isdir(raw_root):
		raise FileNotFoundError(f"未找到原始结果根目录: {raw_root}")
	
	# 确定要处理的文档列表
	if args.document_id:
		doc_ids = [args.document_id]
	else:
		doc_ids = [d for d in os.listdir(raw_root) if os.path.isdir(os.path.join(raw_root, d))]
	
	fields = load_fields(cfg)
	targets = [f['target'] for f in fields if 'target' in f]
	
	logger.info(f"待投票文档数: {len(doc_ids)}")
	
	for doc_id in iter_with_progress(doc_ids, desc='local-vote'):
		doc_dir = os.path.join(raw_root, doc_id)
		if not os.path.isdir(doc_dir):
			logger.warning(f"文档目录不存在: {doc_dir}")
			continue
		
		# 收集所有模型的结果
		model_votes: Dict[str, Dict[str, Dict[str, Any]]] = {}
		
		for model_name in os.listdir(doc_dir):
			model_dir = os.path.join(doc_dir, model_name)
			if not os.path.isdir(model_dir):
				continue
			
			# 读取该模型的所有运行结果
			run_files = [
				fn for fn in os.listdir(model_dir)
				if RUN_FILE_PATTERN.match(fn)
			]
			
			if not run_files:
				logger.warning(f"[{doc_id}] 模型 {model_name} 未找到 run_k.json 文件")
				continue
			
			run_files.sort(key=lambda fn: int(RUN_FILE_PATTERN.match(fn).group(1)))
			runs = [read_json(os.path.join(model_dir, fn)) for fn in run_files]
			
			logger.info(f"[{doc_id}] 模型 {model_name}: {len(runs)} 次运行结果")
			
			# 模型内投票
			mv = model_level_vote(runs, targets=targets, threshold=args.model_level_threshold)
			model_votes[model_name] = mv
		
		if not model_votes:
			logger.warning(f"[{doc_id}] 未找到任何模型结果，跳过")
			continue
		
		# 跨模型投票
		finals, metrics = cross_model_vote(model_votes)
		
		# 保存结果
		consensus_dir = os.path.join(cfg.output_dir, 'consensus', doc_id)
		final_dir = os.path.join(cfg.output_dir, 'final')
		os.makedirs(consensus_dir, exist_ok=True)
		os.makedirs(final_dir, exist_ok=True)
		
		ts = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
		
		# 保存模型级投票结果
		with open(os.path.join(consensus_dir, 'model_level.json'), 'w', encoding='utf-8') as f:
			json.dump(model_votes, f, ensure_ascii=False, indent=2)
		with open(os.path.join(consensus_dir, f'model_level_{ts}.json'), 'w', encoding='utf-8') as f:
			json.dump(model_votes, f, ensure_ascii=False, indent=2)
		
		# 保存最终结果
		final_result = {
			"final_fields": finals,
			"metrics": metrics,
			"models_used": list(model_votes.keys()),
		}
		with open(os.path.join(final_dir, f'{doc_id}.json'), 'w', encoding='utf-8') as f:
			json.dump(final_result, f, ensure_ascii=False, indent=2)
		with open(os.path.join(final_dir, f'{doc_id}_{ts}.json'), 'w', encoding='utf-8') as f:
			json.dump(final_result, f, ensure_ascii=False, indent=2)
		
		logger.info(f"[{doc_id}] 投票完成，使用模型: {list(model_votes.keys())}")
	
	logger.info(f"投票完成！最终结果保存在: {cfg.output_dir}/final/")


def main():
	parser = argparse.ArgumentParser(prog='ensemble_els')
	sub = parser.add_subparsers(dest='cmd')

	# collect
	p_collect = sub.add_parser('collect')
	p_collect.add_argument('--excel', required=True)
	p_collect.add_argument('--text-dir', required=True)
	p_collect.add_argument('--output', default='outputs')
	p_collect.add_argument('--models', nargs='*', default=None)
	p_collect.add_argument('--runs-per-model', type=int, default=None)
	p_collect.add_argument('--limit', type=int, default=0)
	p_collect.set_defaults(func=cmd_collect)

	# vote single
	p_vote = sub.add_parser('vote')
	p_vote.add_argument('--document-id', required=True)
	p_vote.add_argument('--output', default='outputs')
	p_vote.add_argument('--model-level-threshold', type=float, default=0.7)
	p_vote.set_defaults(func=cmd_vote)

	# vote batch
	p_vb = sub.add_parser('vote-batch')
	p_vb.add_argument('--output', default='outputs')
	p_vb.add_argument('--model-level-threshold', type=float, default=0.7)
	p_vb.set_defaults(func=cmd_vote_batch)

	# validate-one
	p_val = sub.add_parser('validate-one')
	p_val.add_argument('--excel', required=False)
	p_val.add_argument('--text-dir', required=True)
	p_val.add_argument('--output', default='outputs')
	p_val.add_argument('--row-index', type=int, default=0)
	p_val.add_argument('--document-id', default=None)
	p_val.add_argument('--models', nargs='*', default=None)
	p_val.set_defaults(func=cmd_validate_one)

	# test-gemini
	p_gemini = sub.add_parser('test-gemini')
	p_gemini.add_argument('--excel', required=True, help='Excel数据文件路径')
	p_gemini.add_argument('--text-dir', required=True, help='文书文本目录')
	p_gemini.add_argument('--output', default='outputs', help='输出目录')
	p_gemini.add_argument('--sample', type=int, default=5, help='随机抽样数量')
	p_gemini.set_defaults(func=cmd_test_gemini)

	# local-collect: 连接本地 vLLM 服务器收集结果
	p_local_collect = sub.add_parser('local-collect', help='连接本地 vLLM 服务器收集模型输出')
	p_local_collect.add_argument('--base-url', default='http://localhost:8000/v1', help='vLLM 服务器地址')
	p_local_collect.add_argument('--model-name', required=True, help='served-model-name (如 qwen3-32b)')
	p_local_collect.add_argument('--excel', required=False, help='Excel数据文件路径')
	p_local_collect.add_argument('--text-dir', required=True, help='文书文本目录')
	p_local_collect.add_argument('--output', default='outputs', help='输出目录')
	p_local_collect.add_argument('--document-id', default=None, help='指定单个文档ID')
	p_local_collect.add_argument('--runs', type=int, default=10, help='每个文档运行次数')
	p_local_collect.add_argument('--limit', type=int, default=0, help='处理文档数量限制')
	p_local_collect.set_defaults(func=cmd_local_collect)

	# local-vote: 对本地收集的结果进行投票
	p_local_vote = sub.add_parser('local-vote', help='对本地收集的多模型结果进行投票')
	p_local_vote.add_argument('--output', default='outputs', help='输出目录')
	p_local_vote.add_argument('--document-id', default=None, help='指定单个文档ID（可选）')
	p_local_vote.add_argument('--model-level-threshold', type=float, default=0.7, help='模型内投票阈值')
	p_local_vote.set_defaults(func=cmd_local_vote)

	args = parser.parse_args()
	if not hasattr(args, 'func'):
		parser.print_help()
		return
	args.func(args)


if __name__ == '__main__':
	main()


