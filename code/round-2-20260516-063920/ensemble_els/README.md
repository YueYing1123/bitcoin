# Ensemble ELS - 多模型一致性抽取框架

多模型投票式信息抽取工具，支持云端 API 和本地 vLLM 服务器。

## 快速开始

### 1. 安装依赖

```bash
cd ensemble_els
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `env.example` 为 `.env` 并填写 API 密钥（云端模式）：

```bash
# 云端 API 密钥（按需配置）
MOONSHOT_API_KEY=xxx      # Kimi
ARK_API_KEY=xxx           # Deepseek / Doubao
DASHSCOPE_API_KEY=xxx     # Qwen
ZHIPUAI_API_KEY=xxx       # GLM

# 本地 vLLM 配置
VLLM_BASE_URL=http://localhost:8000/v1
VLLM_MODEL=qwen3-32b
```

### 3. 准备数据

数据文件位于 `data/` 目录：
- `data/data-index.json` - 索引数据
- `data/data-texts.json` - 文本数据
- `docs/fields.yaml` - 字段配置

> **注**：如需从原始格式（Excel + TXT 目录）转换，可使用转换脚本：
> ```bash
> python -m ensemble_els.scripts.convert_to_json \
>     --excel data-index.xlsx \
>     --text-dir path/to/txt_files \
>     --output-dir data
> ```

---

## 命令一览

### 本地 vLLM 模式（推荐）

**步骤 1：启动 vLLM 服务器**

```bash
python -m vllm.entrypoints.openai.api_server \
    --model /path/to/Qwen3-32B \
    --served-model-name qwen3-32b \
    --port 8000 \
    --gpu-memory-utilization 0.85
```

**步骤 2：收集模型结果**

```bash
# 单个文档（使用 JSON 格式）
python -m ensemble_els.cli local-collect \
    --base-url http://localhost:8000/v1 \
    --model-name qwen3-32b \
    --text-dir data/data-texts.json \
    --document-id "0b4f0764-6063-4808-bd8a-ac8600532336" \
    --runs 10

# 批量处理（使用 JSON 格式）
python -m ensemble_els.cli local-collect \
    --base-url http://localhost:8000/v1 \
    --model-name qwen3-32b \
    --excel data/data-index.json \
    --text-dir data/data-texts.json \
    --runs 10 \
    --limit 100
```

**步骤 3：切换模型后重复步骤 1-2**

```bash
# 重启 vLLM 使用另一个模型
python -m vllm.entrypoints.openai.api_server \
    --model /path/to/Llama3-70B \
    --served-model-name llama3-70b \
    --port 8000

# 再次收集
python -m ensemble_els.cli local-collect \
    --model-name llama3-70b \
    --text-dir data/data-texts.json \
    --document-id "0b4f0764-6063-4808-bd8a-ac8600532336" \
    --runs 10
```

**步骤 4：投票聚合**

```bash
# 对所有模型结果进行投票
python -m ensemble_els.cli local-vote --output outputs

# 指定单个文档
python -m ensemble_els.cli local-vote --document-id "xxx-xxx-xxx"
```

### 云端 API 模式

```bash
# 验证单条
python -m ensemble_els.cli validate-one \
    --excel data/data-index.json \
    --text-dir data/data-texts.json \
    --row-index 0 \
    --models KIMI DEEPSEEK GLM QWEN DOUBAO

# 批量收集
python -m ensemble_els.cli collect \
    --excel data/data-index.json \
    --text-dir data/data-texts.json \
    --models KIMI QWEN \
    --runs-per-model 10 \
    --limit 100

# 投票
python -m ensemble_els.cli vote-batch
```

---

## 输出目录结构

```
outputs/
├── raw/{document_id}/{MODEL}/     # 各模型原始输出
│   ├── run_1.json
│   ├── run_2.json
│   └── ...
├── consensus/{document_id}/       # 模型内投票结果
│   └── model_level.json
└── final/                         # 最终投票结果
    └── {document_id}.json
```

---

## 环境变量参考

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `INDEX_PATH` | - | 索引文件路径（.json 或 .xlsx） |
| `TEXTS_PATH` | - | 文本文件路径（.json 或目录） |
| `VLLM_BASE_URL` | `http://localhost:8000/v1` | vLLM 服务器地址 |
| `VLLM_MODEL` | `qwen3-32b` | 模型名称 |
| `RUNS_PER_MODEL` | `10` | 每个模型运行次数 |
| `OUTPUT_DIR` | `outputs` | 输出目录 |
| `REQUEST_TIMEOUT` | `120` | 请求超时（秒） |
| `MAX_RETRIES` | `12` | 最大重试次数 |
| `LOG_LEVEL` | `INFO` | 日志级别 |

---

## Linux 服务器部署

```bash
# 1. 先在本地转换数据为 JSON 格式
python -m ensemble_els.scripts.convert_to_json

# 2. 上传项目文件夹（精简后的结构）
#    project_root/
#    ├── ensemble_els/           # 核心代码
#    ├── docs/fields.yaml        # 字段定义
#    ├── data/
#    │   ├── data-index.json     # 索引数据（JSON）
#    │   └── data-texts.json     # 文本数据（JSON）
#    └── outputs/                # 输出目录
scp -r project_root user@server:/path/to/

# 3. 安装依赖
cd /path/to/project_root
pip install -r ensemble_els/requirements.txt

# 4. 配置环境变量
cp ensemble_els/env.example .env
vim .env

# 5. 运行
python -m ensemble_els.cli local-collect --help
```

