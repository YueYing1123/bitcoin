# -*- coding: utf-8 -*-
"""
索引数据读取器：支持从 JSON 或 Excel 文件读取记录

支持两种格式：
1. JSON 格式：*.json 文件（推荐，迁移更方便）
2. Excel 格式：*.xlsx 文件（兼容旧格式）
"""
from __future__ import annotations

import os
import json
import pandas as pd
from typing import Iterator, Dict, Any, Optional, List


REQUIRED_COLUMNS = [
    "文书标题",
    "案由/罪名",
    "案号",
    "审结时间",
    "审理法院",
    "法院级别",
    "审理程序",
    "可唯一识别id",
]


def _read_json_records(json_path: str, limit: int = 0) -> Iterator[Dict[str, Any]]:
    """从 JSON 文件读取记录"""
    with open(json_path, 'r', encoding='utf-8') as f:
        records: List[Dict[str, Any]] = json.load(f)
    
    # 检查必要列
    if records:
        missing = [c for c in REQUIRED_COLUMNS if c not in records[0]]
        if missing:
            raise ValueError(f"JSON 缺少必要列: {missing}")
    
    if limit and limit > 0:
        records = records[:limit]
    
    for idx, record in enumerate(records):
        # 确保有 __row_index__
        if "__row_index__" not in record:
            record["__row_index__"] = idx
        yield record


def _read_excel_records(excel_path: str, limit: int = 0) -> Iterator[Dict[str, Any]]:
    """从 Excel 文件读取记录"""
    df = pd.read_excel(excel_path)
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Excel 缺少必要列: {missing}")

    if limit and limit > 0:
        df = df.head(limit)

    for idx, row in df.iterrows():
        record = {c: (None if pd.isna(row[c]) else row[c]) for c in REQUIRED_COLUMNS}
        record["__row_index__"] = int(idx)
        yield record


def read_excel_records(data_path: str, limit: int = 0) -> Iterator[Dict[str, Any]]:
    """
    读取索引记录（自动识别 JSON 或 Excel 格式）
    
    Args:
        data_path: 数据文件路径 (*.json 或 *.xlsx)
        limit: 最大读取记录数，0 表示不限制
    
    Yields:
        记录字典
    """
    if data_path.endswith('.json'):
        yield from _read_json_records(data_path, limit)
    elif data_path.endswith('.xlsx') or data_path.endswith('.xls'):
        yield from _read_excel_records(data_path, limit)
    else:
        # 尝试自动检测
        if os.path.exists(data_path + '.json'):
            yield from _read_json_records(data_path + '.json', limit)
        elif os.path.exists(data_path + '.xlsx'):
            yield from _read_excel_records(data_path + '.xlsx', limit)
        else:
            raise FileNotFoundError(f"未找到数据文件: {data_path}")


def _get_json_row_by_index(json_path: str, row_index: int) -> Dict[str, Any]:
    """从 JSON 文件获取指定行"""
    with open(json_path, 'r', encoding='utf-8') as f:
        records: List[Dict[str, Any]] = json.load(f)
    
    missing = [c for c in REQUIRED_COLUMNS if c not in records[0]]
    if missing:
        raise ValueError(f"JSON 缺少必要列: {missing}")
    
    if row_index < 0 or row_index >= len(records):
        raise IndexError("row_index 超出范围")
    
    record = records[row_index]
    if "__row_index__" not in record:
        record["__row_index__"] = row_index
    return record


def _get_excel_row_by_index(excel_path: str, row_index: int) -> Dict[str, Any]:
    """从 Excel 文件获取指定行"""
    df = pd.read_excel(excel_path)
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Excel 缺少必要列: {missing}")
    if row_index < 0 or row_index >= len(df):
        raise IndexError("row_index 超出范围")
    row = df.iloc[row_index]
    record = {c: (None if pd.isna(row[c]) else row[c]) for c in REQUIRED_COLUMNS}
    record["__row_index__"] = int(row_index)
    return record


def get_row_by_index(data_path: str, row_index: int) -> Dict[str, Any]:
    """
    获取指定行的记录（自动识别 JSON 或 Excel 格式）
    
    Args:
        data_path: 数据文件路径 (*.json 或 *.xlsx)
        row_index: 行索引
    
    Returns:
        记录字典
    """
    if data_path.endswith('.json'):
        return _get_json_row_by_index(data_path, row_index)
    elif data_path.endswith('.xlsx') or data_path.endswith('.xls'):
        return _get_excel_row_by_index(data_path, row_index)
    else:
        # 尝试自动检测
        if os.path.exists(data_path + '.json'):
            return _get_json_row_by_index(data_path + '.json', row_index)
        elif os.path.exists(data_path + '.xlsx'):
            return _get_excel_row_by_index(data_path + '.xlsx', row_index)
        else:
            raise FileNotFoundError(f"未找到数据文件: {data_path}")
