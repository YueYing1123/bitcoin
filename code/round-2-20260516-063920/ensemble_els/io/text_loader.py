# -*- coding: utf-8 -*-
"""
文本加载器：支持从 JSON 文件或 TXT 目录加载文档文本

支持两种模式：
1. JSON 模式：从单个 JSON 文件加载（推荐，迁移更方便）
2. TXT 目录模式：从目录中的 {document_id}.txt 文件加载（兼容旧格式）
"""
from __future__ import annotations

import os
import json
from typing import Optional, Dict

# 全局缓存，避免重复加载 JSON 文件
_texts_cache: Optional[Dict[str, str]] = None
_texts_cache_path: Optional[str] = None


def read_text_with_fallback(path: str) -> str:
    """尝试多种常见编码读取文本文件"""
    for enc in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except Exception:
            continue
    raise RuntimeError(f"无法以常见编码读取文件: {path}")


def _load_texts_json(json_path: str) -> Dict[str, str]:
    """加载 JSON 格式的文本文件"""
    global _texts_cache, _texts_cache_path
    
    # 如果已缓存且路径相同，直接返回
    if _texts_cache is not None and _texts_cache_path == json_path:
        return _texts_cache
    
    with open(json_path, 'r', encoding='utf-8') as f:
        _texts_cache = json.load(f)
        _texts_cache_path = json_path
    
    return _texts_cache


def load_document_text(text_source: str, document_id: str) -> str:
    """
    加载文档文本
    
    Args:
        text_source: 文本来源，可以是：
            - JSON 文件路径 (*.json)
            - TXT 文件目录
        document_id: 文档 ID
    
    Returns:
        文档文本内容
    
    Raises:
        FileNotFoundError: 未找到对应文档
    """
    # 判断是 JSON 文件还是目录
    if text_source.endswith('.json') and os.path.isfile(text_source):
        # JSON 模式
        texts = _load_texts_json(text_source)
        if document_id in texts:
            return texts[document_id]
        raise FileNotFoundError(f"未找到文档 {document_id} 于 JSON 文件: {text_source}")
    
    elif os.path.isdir(text_source):
        # TXT 目录模式（兼容旧格式）
        for name in (f"{document_id}.txt", document_id):
            full = os.path.join(text_source, name)
            if os.path.isfile(full):
                return read_text_with_fallback(full)
        raise FileNotFoundError(f"未找到对应文书: {document_id} 于 {text_source}")
    
    else:
        raise FileNotFoundError(f"无效的文本来源: {text_source} (既不是 JSON 文件也不是目录)")


def clear_cache():
    """清除文本缓存"""
    global _texts_cache, _texts_cache_path
    _texts_cache = None
    _texts_cache_path = None
