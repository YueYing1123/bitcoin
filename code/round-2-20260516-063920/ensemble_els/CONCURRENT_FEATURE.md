# 并发功能使用说明

## 概述

ensemble_els 现已支持完整的异步并发执行功能，可以显著提升数据采集效率。主要特性包括：

1. **模型间并发**：5个模型（KIMI、DEEPSEEK、DOUBAO、QWEN、GLM）完全并行执行
2. **模型内并发**：每个模型的多次运行（`RUNS_PER_MODEL`）也并行执行
3. **独立速率限制**：每个模型可以独立配置 RPM（每分钟请求数）和 TPM（每分钟令牌数）限制

## 配置方法

### 1. 安装依赖

首先安装新增的依赖：

```bash
pip install -r requirements.txt
```

主要新增依赖：`aiolimiter>=1.1.0`

### 2. 配置 .env 文件

在项目根目录创建 `.env` 文件（参考 `env.example`），添加速率限制配置：

```bash
# KIMI 模型配置
KIMI_RPM=60              # 每分钟最多60个请求
KIMI_TPM=30000           # 每分钟最多30000个token
KIMI_MAX_CONCURRENT=5    # 该模型内部最多同时执行5个runs

# DEEPSEEK 模型配置
DEEPSEEK_RPM=60
DEEPSEEK_TPM=30000
DEEPSEEK_MAX_CONCURRENT=5

# DOUBAO 模型配置
DOUBAO_RPM=60
DOUBAO_TPM=30000
DOUBAO_MAX_CONCURRENT=5

# QWEN 模型配置
QWEN_RPM=60
QWEN_TPM=30000
QWEN_MAX_CONCURRENT=5

# GLM 模型配置
GLM_RPM=60
GLM_TPM=30000
GLM_MAX_CONCURRENT=5
```

**配置说明**：
- **RPM/TPM**：设置为 `0` 表示不限制（但仍受API实际限制）
- **MAX_CONCURRENT**：
  - 设置为 `0`：该模型的所有 runs 完全并发执行（最快）
  - 设置为 `N`：该模型最多同时执行 N 个 runs
  - 例如：`RUNS_PER_MODEL=10, KIMI_MAX_CONCURRENT=5` 表示分2批执行，每批5个
- 每个模型的配置是独立的，互不影响
- 所有模型之间默认全部并发执行

## 工作原理

### 并发架构

```
文档1
├── 模型1 (KIMI)      ──┐ 
│   ├── 运行1          │ 模型间
│   ├── 运行2          │ 全部并发
│   └── 运行N          │
│   (MAX_CONCURRENT控制内部并发数)
│
├── 模型2 (DEEPSEEK)  ──┤
│   ├── 运行1          │ 
│   ├── 运行2          │ 
│   └── 运行N          │
│
├── 模型3 (DOUBAO)    ──┤ 同时
├── 模型4 (QWEN)      ──┤ 执行
└── 模型5 (GLM)       ──┘
```

**并发层次**：
1. **模型间并发**：5个模型同时执行（不可配置，默认全部并发）
2. **模型内并发**：每个模型的 N 个 runs 可配置并发数
   - `MAX_CONCURRENT=0`：所有 runs 同时执行
   - `MAX_CONCURRENT=N`：最多 N 个 runs 同时执行，其余排队

### 速率限制与并发控制机制

#### 1. 速率限制（基于 `aiolimiter`）

**RPM 限制**：控制每分钟的请求次数
- 使用滑动窗口算法
- 时间窗口：60秒
- 当达到限制时，请求会自动排队等待

**TPM 限制**：控制每分钟的令牌消耗
- 预估每个请求约消耗2000个token（可调整）
- 同样使用滑动窗口算法
- 可以一次性"购买"多个token的额度

#### 2. 并发控制（基于 `asyncio.Semaphore`）

**MAX_CONCURRENT 参数**：控制单个模型内部的并发数
- 使用信号量（Semaphore）机制
- 限制同时执行的任务数量
- 超出限制的任务会等待有空闲槽位

**示例**：
```python
# 假设 RUNS_PER_MODEL=10, KIMI_MAX_CONCURRENT=3
# 执行顺序：
运行1, 运行2, 运行3  →  同时执行（占用3个槽位）
运行4, 运行5, 运行6  →  等前3个完成后执行
运行7, 运行8, 运行9  →  等前一批完成后执行
运行10              →  等前一批完成后执行
```

#### 3. 独立性

- 每个模型有自己独立的速率限制器和并发控制器
- 模型A达到限制不影响模型B
- 充分利用多模型的API配额

## 性能提升

### 示例场景

假设配置如下：
- 5个模型
- 每个模型运行10次 (RUNS_PER_MODEL=10)
- 每个请求平均耗时30秒

**串行执行**（旧版本）：
```
总时间 = 5 × 10 × 30秒 = 1500秒 = 25分钟
```

**并发执行**（新版本）：
```
总时间 ≈ max(10次运行的速率限制时间) ≈ 10 × (60/RPM)秒
如果 RPM=60，则约 10秒（理想情况）
实际受TPM限制，约 1-3分钟
```

**提升倍数**：约 **8-25倍加速**

## 使用示例

### 基本使用

```bash
# 使用并发模式采集数据
python -m ensemble_els.cli collect \
    --excel 比特币数据.xlsx \
    --text-dir 金融课题研究案例-比特币/金融课题案例数据全文 \
    --output outputs \
    --runs-per-model 10
```

系统会自动：
1. 读取 `.env` 中的速率限制配置
2. 为每个模型创建独立的速率限制器
3. 使用异步并发模式执行

### 监控并发执行

启用详细日志查看并发执行情况：

```bash
# 在 .env 中设置
LOG_LEVEL=DEBUG
```

日志输出示例：
```
[INFO] 模型 KIMI 配置速率限制: RPM=60, TPM=30000
[INFO] 模型 DEEPSEEK 配置速率限制: RPM=60, TPM=30000
[INFO] [doc123] 开始并发处理 5 个模型，每个模型 10 次运行
[DEBUG] KIMI 获取速率限制许可成功 (预估 2000 tokens)
[INFO] [doc123] 模型 KIMI 第 1 次运行开始
[INFO] [doc123] 模型 DEEPSEEK 第 1 次运行开始
...
[INFO] [doc123] 所有模型处理完成
```

## 高级配置

### 调整预估Token数

在 `ensemble_els/cli.py` 中修改 `estimated_tokens` 参数：

```python
res = await client.generate_async(
    document_id=document_id,
    meta=record,
    document_text=text,
    fields=fields,
    estimated_tokens=3000  # 根据实际情况调整
)
```

### 禁用速率限制

如果不需要速率限制，只需不配置或设置为0：

```bash
# 不配置速率限制，或设置为0
KIMI_RPM=0
KIMI_TPM=0
```

系统会自动使用 `NoOpRateLimiter`，不会限制速率。

### 向后兼容

如果遇到任何问题，仍可使用同步模式（通过修改 `cli.py` 中的 `use_async` 标志）。

## 故障排查

### 1. ImportError: 需要安装 aiolimiter 库

```bash
pip install aiolimiter>=1.1.0
```

### 2. 速率限制过于严格

- 检查 `.env` 中的 RPM/TPM 配置
- 适当增加限制值
- 或设置为 0 禁用限制

### 3. 并发执行异常

- 检查日志输出（设置 `LOG_LEVEL=DEBUG`）
- 确认所有模型的 API Key 正确配置
- 检查网络连接

## 技术细节

### 核心文件

1. **`ensemble_els/config.py`**
   - 添加 `ModelRateLimit` 数据类
   - 在 `RuntimeConfig` 中添加 `rate_limits` 字段
   - 从环境变量读取各模型的 RPM/TPM 配置

2. **`ensemble_els/utils/rate_limiter.py`**
   - `ModelRateLimiter`：基于 `aiolimiter` 的速率限制器
   - `NoOpRateLimiter`：空操作限制器（用于不限制时）

3. **`ensemble_els/llm/base.py`**
   - 在 `LLMClientBase` 中添加 `rate_limiter` 参数
   - 添加 `generate_async()` 异步方法
   - 使用 `asyncio.run_in_executor` 桥接同步API

4. **`ensemble_els/llm/*.py`**
   - 所有客户端（KIMI、DEEPSEEK、DOUBAO、QWEN、GLM）
   - 添加 `rate_limiter` 参数支持

5. **`ensemble_els/cli.py`**
   - `make_clients()`：为每个客户端创建独立限制器
   - `collect_for_doc_async()`：异步并发采集函数
   - `cmd_collect()`：支持异步模式的命令入口

### 异步执行流程

```python
# 伪代码
async def collect_for_doc_async(...):
    # 为每个模型创建并发任务
    model_tasks = [
        run_model_concurrent(model, client, runs)
        for model, client in clients.items()
    ]
    # 并发执行所有模型
    await asyncio.gather(*model_tasks)

async def run_model_concurrent(model, client, runs):
    # 该模型的所有运行并发执行
    tasks = [run_once(k) for k in range(1, runs + 1)]
    await asyncio.gather(*tasks)

async def run_once(run_index):
    # 获取速率限制许可
    await rate_limiter.acquire(estimated_tokens)
    # 执行API调用
    result = await client.generate_async(...)
    # 保存结果
    save_result(result)
```

## 最佳实践

1. **合理配置速率限制**
   - 不要设置得过于宽松，避免触发API限流
   - 也不要过于保守，影响并发效率
   - 建议设置为API限制的 80-90%

2. **监控执行情况**
   - 使用 `LOG_LEVEL=INFO` 监控整体进度
   - 使用 `LOG_LEVEL=DEBUG` 调试速率限制问题

3. **分批处理大量文档**
   - 对于大量文档，建议分批处理
   - 每批次完成后检查结果
   - 避免一次性提交过多任务

4. **备份配置**
   - 保留 `env.example` 作为配置模板
   - 定期备份 `.env` 文件（但不要提交到版本控制）

## 更新日志

### v2.0.0 (2025-11-28)

- ✨ 新增：模型间完全并发执行
- ✨ 新增：模型内部多次运行并发执行
- ✨ 新增：基于 aiolimiter 的精确速率限制
- ✨ 新增：每个模型独立的 RPM/TPM 配置
- 🔧 修改：CLI 支持异步执行模式
- 🔧 修改：所有 LLM 客户端支持异步调用
- 📝 新增：详细的配置文档和使用说明
- ⚡ 性能：预期 8-25倍执行速度提升

---

**如有问题或建议，请查看项目文档或联系维护者。**

