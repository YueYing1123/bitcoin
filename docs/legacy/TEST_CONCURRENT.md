# 并发模式测试指南

## 快速测试单条数据

### 方法一：使用文档ID测试（推荐）

如果您知道文档的唯一标识ID：

```bash
python -m ensemble_els.cli validate-one \
    --document-id "05e5c09f-7497-48cf-a5bb-b2920163446d" \
    --text-dir "金融课题研究案例-比特币/金融课题案例数据全文" \
    --output outputs_test
```

### 方法二：使用Excel行索引测试

从Excel文件读取指定行（索引从0开始）：

```bash
python -m ensemble_els.cli validate-one \
    --excel "比特币数据.xlsx" \
    --text-dir "金融课题研究案例-比特币/金融课题案例数据全文" \
    --row-index 0 \
    --output outputs_test
```

### 方法三：只测试部分模型

```bash
python -m ensemble_els.cli validate-one \
    --document-id "05e5c09f-7497-48cf-a5bb-b2920163446d" \
    --text-dir "金融课题研究案例-比特币/金融课题案例数据全文" \
    --models KIMI DEEPSEEK \
    --output outputs_test
```

## 测试不同的并发配置

### 配置1：完全并发（最快）

在 `.env` 中设置：

```bash
# 所有模型完全并发，无限制
KIMI_MAX_CONCURRENT=0
DEEPSEEK_MAX_CONCURRENT=0
DOUBAO_MAX_CONCURRENT=0
QWEN_MAX_CONCURRENT=0
GLM_MAX_CONCURRENT=0
```

**预期效果**：所有模型的所有 runs 同时开始执行

### 配置2：适度并发（推荐）

```bash
# 每个模型最多5个并发
KIMI_MAX_CONCURRENT=5
DEEPSEEK_MAX_CONCURRENT=5
DOUBAO_MAX_CONCURRENT=5
QWEN_MAX_CONCURRENT=5
GLM_MAX_CONCURRENT=5
```

**预期效果**：每个模型内部最多5个 runs 同时执行

### 配置3：保守并发（稳定）

```bash
# 每个模型最多2个并发
KIMI_MAX_CONCURRENT=2
DEEPSEEK_MAX_CONCURRENT=2
DOUBAO_MAX_CONCURRENT=2
QWEN_MAX_CONCURRENT=2
GLM_MAX_CONCURRENT=2
```

**预期效果**：每个模型内部最多2个 runs 同时执行，更稳定

### 配置4：差异化并发（灵活）

```bash
# 不同模型配置不同的并发数
KIMI_MAX_CONCURRENT=10      # KIMI稳定性好，全部并发
DEEPSEEK_MAX_CONCURRENT=5   # DEEPSEEK适中
DOUBAO_MAX_CONCURRENT=3     # DOUBAO保守
QWEN_MAX_CONCURRENT=0       # QWEN不限制
GLM_MAX_CONCURRENT=2        # GLM最保守
```

**预期效果**：根据各模型API的稳定性灵活配置

## 观察并发执行

### 1. 启用详细日志

在 `.env` 中设置：

```bash
LOG_LEVEL=INFO
```

或者更详细的调试信息：

```bash
LOG_LEVEL=DEBUG
```

### 2. 关键日志输出

运行测试时，您会看到类似输出：

```
[INFO] 模型 KIMI 配置速率限制: RPM=60, TPM=30000
[INFO] 模型 KIMI 配置最大并发数: 5
[INFO] [doc123] 开始并发处理 5 个模型，每个模型 10 次运行
[INFO] [doc123] 模型 KIMI 无并发限制（全部并发）
[INFO] [doc123] 模型 DEEPSEEK 配置最大并发数: 5
[INFO] [doc123] 模型 KIMI 第 1 次运行开始
[INFO] [doc123] 模型 KIMI 第 2 次运行开始
[INFO] [doc123] 模型 DEEPSEEK 第 1 次运行开始
...
[INFO] [doc123] 模型 KIMI 第 1 次运行完成
[INFO] [doc123] 所有模型处理完成
```

### 3. 验证并发效果

**查看时间戳**：
- 如果多个 "运行开始" 的时间戳非常接近 → 并发生效
- 如果 "运行开始" 时间间隔较大 → 串行执行或受限流影响

**查看结果目录**：

```bash
# 查看原始输出
ls -lt outputs_test/raw/doc_id/KIMI/

# 每个 run 会生成带时间戳的文件
# run_1_20251128-143025-123456.json
# run_2_20251128-143025-234567.json
# 时间戳接近说明并发执行
```

## 完整测试流程

### 步骤1：准备环境

```bash
# 安装依赖
pip install -r requirements.txt

# 复制配置文件
cp env.example .env

# 编辑 .env，填入您的API密钥
# 配置并发参数
```

### 步骤2：配置测试参数

在 `.env` 中设置：

```bash
# 设置较小的运行次数以便快速测试
RUNS_PER_MODEL=5

# 配置并发数
KIMI_MAX_CONCURRENT=2
DEEPSEEK_MAX_CONCURRENT=2

# 启用详细日志
LOG_LEVEL=INFO
```

### 步骤3：运行测试

```bash
python -m ensemble_els.cli validate-one \
    --document-id "your_doc_id_here" \
    --text-dir "path/to/text/dir" \
    --models KIMI DEEPSEEK \
    --output outputs_test
```

### 步骤4：检查结果

```bash
# 查看原始输出
ls -la outputs_test/raw/your_doc_id/

# 查看最终结果
cat outputs_test/final/your_doc_id.json
```

## 性能对比测试

### 测试不同配置的执行时间

```bash
# 测试1：完全并发
time python -m ensemble_els.cli validate-one \
    --document-id "doc_id" \
    --text-dir "text_dir" \
    --output outputs_test1

# 测试2：限制并发=5
# 修改 .env: KIMI_MAX_CONCURRENT=5
time python -m ensemble_els.cli validate-one \
    --document-id "doc_id" \
    --text-dir "text_dir" \
    --output outputs_test2

# 测试3：限制并发=2
# 修改 .env: KIMI_MAX_CONCURRENT=2
time python -m ensemble_els.cli validate-one \
    --document-id "doc_id" \
    --text-dir "text_dir" \
    --output outputs_test3
```

### 分析结果

比较三次测试的执行时间：
- 完全并发应该最快（但可能触发限流）
- 适度并发（5）是平衡点
- 保守并发（2）最慢但最稳定

## 常见问题

### Q1: 看不到并发效果？

**检查项**：
1. 确认 `.env` 中 `MAX_CONCURRENT` 设置正确
2. 查看日志，确认配置已加载
3. 检查是否所有模型都成功创建客户端

### Q2: 遇到 API 限流错误？

**解决方案**：
1. 减小 `MAX_CONCURRENT` 值
2. 降低 `RPM` 和 `TPM` 限制
3. 增加 `BACKOFF_BASE` 重试间隔

### Q3: 部分 runs 失败？

**可能原因**：
1. API 密钥配置错误
2. 网络不稳定
3. API 限流

**解决方案**：
- 检查日志中的错误信息
- 减小并发数
- 启用 `LOG_LEVEL=DEBUG` 查看详细信息

## 生产环境建议

### 推荐配置

```bash
# 生产环境推荐配置
RUNS_PER_MODEL=10

# 根据API套餐设置速率限制（略低于实际限制）
KIMI_RPM=50
KIMI_TPM=25000
KIMI_MAX_CONCURRENT=5

DEEPSEEK_RPM=50
DEEPSEEK_TPM=25000
DEEPSEEK_MAX_CONCURRENT=5

# 其他模型类似...

# 日志级别
LOG_LEVEL=INFO

# 重试配置
MAX_RETRIES=15
BACKOFF_BASE=2.0
REQUEST_TIMEOUT=120
```

### 监控指标

运行时关注：
1. **成功率**：各模型的 runs 成功比例
2. **执行时间**：单个文档的总处理时间
3. **限流频率**：是否频繁触发 API 限流
4. **内存使用**：并发数过高可能导致内存压力

---

**提示**：从小规模测试开始，逐步增加并发数，找到最适合您的配置！

