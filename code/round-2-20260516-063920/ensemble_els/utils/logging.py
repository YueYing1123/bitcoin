# -*- coding: utf-8 -*-
import logging
import os
from typing import Optional


def setup_logging(level: str = "INFO", log_file: Optional[str] = None) -> None:
	level_value = getattr(logging, level.upper(), logging.INFO)
	logging.basicConfig(
		level=level_value,
		format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
	)
	if log_file:
		try:
			fh = logging.FileHandler(log_file, encoding='utf-8')
			fh.setLevel(level_value)
			formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(name)s | %(message)s')
			fh.setFormatter(formatter)
			logging.getLogger().addHandler(fh)
		except Exception:
			# 文件日志失败不应阻断
			pass


