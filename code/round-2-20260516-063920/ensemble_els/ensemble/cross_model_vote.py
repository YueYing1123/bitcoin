# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Dict, Any, List, Tuple
from collections import Counter
import json


def _serialize_value(value: Any) -> str | Any:
	if isinstance(value, (dict, list)):
		try:
			return json.dumps(value, ensure_ascii=False, sort_keys=True)
		except Exception:
			return str(value)
	return value


def cross_model_vote(model_votes: Dict[str, Dict[str, Dict[str, Any]]]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
	"""
	model_votes: { MODEL: { target_path: {"value": any, "support": float, "accepted": bool} } }
	return: (final_fields_by_target, metrics)
	"""
	finals: Dict[str, Any] = {}
	agreement_sum = 0.0
	count_targets = 0

	# collect all targets
	all_targets: List[str] = sorted({t for mv in model_votes.values() for t in mv.keys()})
	for target in all_targets:
		ser_vals: List[str | Any] = []
		key_to_original: Dict[str | Any, Any] = {}
		for model, mv in model_votes.items():
			if target in mv:
				v = mv[target]["value"]
				k = _serialize_value(v)
				ser_vals.append(k)
				# 记录原值（首次出现即可）
				if k not in key_to_original:
					key_to_original[k] = v
		if not ser_vals:
			continue
		count_targets += 1
		c = Counter(ser_vals)
		top_key, cnt = c.most_common(1)[0]
		agr = cnt / max(1, len(ser_vals))
		agreement_sum += agr
		# 反序列化到原始值
		finals[target] = key_to_original.get(top_key, top_key)

	metrics = {
		"agreement_rate": (agreement_sum / max(1, count_targets)) if count_targets else 0.0,
		"final_label_source": "majority_vote",
	}
	return finals, metrics


