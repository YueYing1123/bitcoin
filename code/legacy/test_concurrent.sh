#!/bin/bash
# ===========================================
# 并发模式测试脚本
# ===========================================

echo "======================================"
echo "测试单条数据的并发模式"
echo "======================================"

# 设置测试参数
DOCUMENT_ID="05e5c09f-7497-48cf-a5bb-b2920163446d"
TEXT_DIR="金融课题研究案例-比特币/金融课题案例数据全文"
OUTPUT_DIR="outputs_test"

echo ""
echo "测试配置："
echo "  文档ID: $DOCUMENT_ID"
echo "  文本目录: $TEXT_DIR"
echo "  输出目录: $OUTPUT_DIR"
echo ""

# 检查必需文件
if [ ! -f ".env" ]; then
    echo "❌ 错误: 未找到 .env 文件"
    echo "   请复制 env.example 为 .env 并配置API密钥"
    exit 1
fi

if [ ! -d "$TEXT_DIR" ]; then
    echo "⚠️  警告: 文本目录不存在: $TEXT_DIR"
    echo "   如果您的路径不同，请修改此脚本"
fi

echo "开始测试..."
echo ""

# 运行测试命令
python -m ensemble_els.cli validate-one \
    --document-id "$DOCUMENT_ID" \
    --text-dir "$TEXT_DIR" \
    --output "$OUTPUT_DIR" \
    --models KIMI DEEPSEEK

echo ""
echo "======================================"
echo "测试完成！"
echo "======================================"
echo ""
echo "查看结果："
echo "  原始输出: $OUTPUT_DIR/raw/$DOCUMENT_ID/"
echo "  共识结果: $OUTPUT_DIR/consensus/$DOCUMENT_ID/"
echo "  最终结果: $OUTPUT_DIR/final/$DOCUMENT_ID.json"
echo ""

