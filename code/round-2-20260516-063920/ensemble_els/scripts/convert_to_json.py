# -*- coding: utf-8 -*-
"""
数据转换脚本：将 Excel 和 TXT 文件转换为 JSON 格式

功能：
1. 将 data-index.xlsx 转换为 data-index.json
2. 将 data/dataset/*.txt 合并为 data-texts.json

使用方法：
    cd 项目根目录
    python -m ensemble_els.scripts.convert_to_json

或指定路径：
    python -m ensemble_els.scripts.convert_to_json \
        --excel data-index.xlsx \
        --text-dir data/dataset \
        --output-dir data
"""
from __future__ import annotations

import os
import json
import argparse
import pandas as pd
from typing import Dict, Any, List
from datetime import datetime


def read_text_with_fallback(path: str) -> str:
    """尝试多种编码读取文本文件"""
    for enc in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except Exception:
            continue
    raise RuntimeError(f"无法以常见编码读取文件: {path}")


def convert_excel_to_json(excel_path: str, output_path: str) -> int:
    """
    将 Excel 文件转换为 JSON 格式
    
    Returns:
        转换的记录数
    """
    print(f"正在读取 Excel: {excel_path}")
    df = pd.read_excel(excel_path)
    
    # 转换 NaN 为 None，日期为字符串
    records = []
    for idx, row in df.iterrows():
        record = {}
        for col in df.columns:
            val = row[col]
            if pd.isna(val):
                record[col] = None
            elif isinstance(val, pd.Timestamp):
                record[col] = val.strftime('%Y-%m-%d %H:%M:%S')
            else:
                record[col] = val
        record["__row_index__"] = int(idx)
        records.append(record)
    
    # 保存为 JSON
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    
    print(f"已保存 {len(records)} 条记录到: {output_path}")
    return len(records)


def convert_texts_to_json(text_dir: str, output_path: str) -> int:
    """
    将目录下的所有 TXT 文件合并为一个 JSON 文件
    
    JSON 结构: { "document_id": "文本内容", ... }
    
    Returns:
        转换的文件数
    """
    print(f"正在扫描文本目录: {text_dir}")
    
    texts: Dict[str, str] = {}
    txt_files = [f for f in os.listdir(text_dir) if f.endswith('.txt')]
    
    for filename in txt_files:
        doc_id = filename[:-4]  # 去掉 .txt 后缀
        filepath = os.path.join(text_dir, filename)
        try:
            content = read_text_with_fallback(filepath)
            texts[doc_id] = content
        except Exception as e:
            print(f"  警告: 无法读取 {filename}: {e}")
    
    # 保存为 JSON
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(texts, f, ensure_ascii=False, indent=2)
    
    print(f"已合并 {len(texts)} 个文本文件到: {output_path}")
    return len(texts)


def main():
    parser = argparse.ArgumentParser(
        description='将 Excel 和 TXT 文件转换为 JSON 格式'
    )
    parser.add_argument(
        '--excel', 
        default='data-index.xlsx',
        help='Excel 索引文件路径 (默认: data-index.xlsx)'
    )
    parser.add_argument(
        '--text-dir', 
        default='data/dataset',
        help='TXT 文本目录路径 (默认: data/dataset)'
    )
    parser.add_argument(
        '--output-dir', 
        default='data',
        help='输出目录 (默认: data)'
    )
    parser.add_argument(
        '--index-output',
        default=None,
        help='索引 JSON 输出文件名 (默认: data-index.json)'
    )
    parser.add_argument(
        '--texts-output',
        default=None,
        help='文本 JSON 输出文件名 (默认: data-texts.json)'
    )
    
    args = parser.parse_args()
    
    # 确保输出目录存在
    os.makedirs(args.output_dir, exist_ok=True)
    
    # 确定输出文件路径
    index_output = args.index_output or os.path.join(args.output_dir, 'data-index.json')
    texts_output = args.texts_output or os.path.join(args.output_dir, 'data-texts.json')
    
    print("=" * 50)
    print("数据转换工具")
    print("=" * 50)
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 转换 Excel
    if os.path.exists(args.excel):
        convert_excel_to_json(args.excel, index_output)
    else:
        print(f"警告: Excel 文件不存在: {args.excel}")
    
    print()
    
    # 转换 TXT 文件
    if os.path.isdir(args.text_dir):
        convert_texts_to_json(args.text_dir, texts_output)
    else:
        print(f"警告: 文本目录不存在: {args.text_dir}")
    
    print()
    print("=" * 50)
    print("转换完成！")
    print()
    print("新的数据文件:")
    print(f"  - 索引文件: {index_output}")
    print(f"  - 文本文件: {texts_output}")
    print()
    print("请更新 .env 文件中的配置:")
    print(f"  INDEX_PATH={index_output}")
    print(f"  TEXTS_PATH={texts_output}")
    print("=" * 50)


if __name__ == '__main__':
    main()

