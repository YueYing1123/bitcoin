# -*- coding: utf-8 -*-
from __future__ import annotations
import json
from collections import Counter, defaultdict
from typing import Any, Dict, List, Tuple


def get_by_path(obj: Dict[str, Any], path: str) -> Any:
	"""
	通过点分隔路径获取值。
	智能处理两种LLM返回格式：
	1. 直接值: obj.field = "value"
	2. 对象格式: obj.field = {"value": "value", "confidence": 0.9}
	
	优先尝试直接路径，如果值是包含'value'键的字典，则提取其中的value。
	"""
	cur: Any = obj
	for key in path.split('.'):
		if not isinstance(cur, dict) or key not in cur:
			return None
		cur = cur[key]
	
	# 如果返回值是包含'value'键的字典，提取value
	if isinstance(cur, dict) and 'value' in cur and 'confidence' in cur:
		return cur['value']
	
	return cur


def normalize_value(value: Any) -> Any:
 	if isinstance(value, str):
 		return value.strip()
 	return value


def majority_vote(values: List[Any]) -> Tuple[Any, float]:
 	if not values:
 		return None, 0.0
 	vals = [json.dumps(v, ensure_ascii=False, sort_keys=True) if isinstance(v, (dict, list)) else v for v in values]
 	c = Counter(vals)
 	most, cnt = c.most_common(1)[0]
 	frac = cnt / max(1, len(values))
 	try:
 		return json.loads(most) if isinstance(most, str) and most.startswith('{') or most.startswith('[') else most, frac
 	except Exception:
 		return most, frac


def model_level_vote(runs: List[Dict[str, Any]], targets: List[str], threshold: float = 0.7) -> Dict[str, Dict[str, Any]]:
	"""
	返回: { target_path: {"value": any, "support": float} }
	"""
	result: Dict[str, Dict[str, Any]] = {}
	for target in targets:
		values = []
		for r in runs:
			values.append(normalize_value(get_by_path(r, target)))
		val, frac = majority_vote(values)
		# 只有当所有值都是None时才跳过（意味着字段不存在）
		# 如果至少有一个模型返回了非None值，或者多数模型返回None，都应该保留
		if val is None and frac == 0.0:
			# 所有值都是None，且没有一致性，说明字段可能不存在
			continue
		result[target] = {"value": val, "support": frac, "accepted": frac >= threshold}
	return result


