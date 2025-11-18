# Claude DeepWiki

> 智能代码仓库分析工具，支持 Claude Agent SDK 和 OpenAI Agents SDK，自动生成业务导向的项目知识库

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 若希望了解更多AI探索相关的内容，可关注作者公众号

<img src="https://wechat-account-1251781786.cos.ap-guangzhou.myqcloud.com/wechat_account.jpeg" width="30%">

## 📖 项目背景

在 AI 辅助编程时代，**需求质量**成为影响开发效率的关键因素。要让 AI 准确理解需求，首先需要让它掌握项目的背景知识。然而：

- 🔒 **Devin.ai 的 DeepWiki** 效果出色，但闭源且仅支持 GitHub 托管的公开仓库
- 📉 **开源版 open-deepwiki** 分析效果有限，难以满足生产需求

因此，我们打造了这个工具，旨在：

- ✅ 本地运行，支持任何代码仓库（公开/私有）
- ✅ 深度理解业务逻辑，生成面向产品的 PRD 文档
- ✅ 多语言支持（165+ 编程语言）
- ✅ 双 SDK 支持：可选 Claude Agent SDK 或 OpenAI Agents SDK

## 🎯 设计理念

### 1. 双 Agent SDK 支持

支持两种强大的 Agent 框架：

- **Claude Agent SDK**：Anthropic 官方的 Agent 框架，强大的推理能力
- **OpenAI Agents SDK**：OpenAI 的 Agents 框架，支持 GPT-4 系列模型

通过配置文件即可切换，无需修改代码。

### 2. 三阶段多 Agent 协作

```
📊 结构扫描 → 🧠 语义分析 → 📄 文档生成
```

**阶段 1: Structure Scanner Agent**

- 扫描项目结构，识别模块层次
- 分析文件依赖关系
- 智能判断模块分层（core/business/utils）

**阶段 2: Semantic Analyzer Agent**

- 概览分析：理解模块的业务价值
- 细节分析：深入挖掘函数/类的业务逻辑（智能分批处理）
- 提取跨文件的业务关系

**阶段 3: Doc Generator Agent**

- 产品功能域智能分组
- 生成业务导向的 PRD 文档
- 质量验证（防止技术术语泄漏）

### 3. MCP 工具标准化

通过 **MCP (Model Context Protocol)** 封装 6 个核心工具：

```python
@tool
def scan_repository_structure(repo_path: str) -> dict:
    """扫描仓库目录结构，识别文件类型和模块组织"""

@tool
def extract_imports_and_exports(file_path: str, language: str) -> dict:
    """提取文件的导入导出关系（基于 Tree-sitter）"""

@tool
def analyze_code_block(code: str, language: str) -> dict:
    """深度分析代码块的 AST 结构和语义"""

@tool
def build_dependency_graph(files_data: list) -> dict:
    """构建模块依赖图"""

@tool
def search_code_patterns(repo_path: str, pattern: str) -> list:
    """搜索特定代码模式（如配置、常量定义）"""

@tool
def validate_analysis_result(analysis: dict) -> dict:
    """验证分析结果的完整性和准确性"""
```

### 4. 核心技术亮点

- **🌐 语言无关**：基于 Tree-sitter 的统一 AST 解析（165+ 语言）
- **🎯 业务视角**：AI 自动提炼技术代码背后的业务价值
- **📦 批处理策略**：智能分批 + token 估算，处理大型项目
- **🔗 精确映射**：每个功能点都关联到具体源码文件
- **🔄 自动重试**：智能检测 JSON 解析错误和分组遗漏，自动重试修正
- **✅ 质量保证**：多重验证机制，防止 AI 幻觉

## 🚀 快速开始

### 环境要求

- Python 3.11+
- 二选一：
  - Claude API Key（使用 Claude Agent SDK）
  - OpenAI API Key（使用 OpenAI Agents SDK，支持 OpenAI 兼容的第三方 API）

### 安装步骤

```bash
# 1. 克隆仓库
git clone https://github.com/your-username/claude-deep-wiki.git
cd claude-deep-wiki

# 2. 创建虚拟环境
python3.11 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置 Agent SDK 和 API Key（推荐使用 .env 文件）
cp .env.example .env
# 编辑 .env 文件，填入你的配置
```

### 配置说明

支持两种方式配置：环境变量（推荐）或修改配置文件。

#### 使用 OpenAI Agents SDK（默认）

```bash
# .env 文件或环境变量
export AGENT_SDK="openai"                 # 选择使用 OpenAI SDK（默认值）
export OPENAI_API_KEY="your-api-key"

# （可选）自定义 API 地址（支持 Azure OpenAI、DeepSeek、Ollama 等 OpenAI 兼容 API）
export OPENAI_BASE_URL="https://your-custom-endpoint.com/v1"

# （可选）自定义模型名称和参数
export OPENAI_MODEL="gpt-4o"              # 默认: gpt-4o
export MODEL_TEMPERATURE="0.7"            # 默认: 0.7，范围 0.0-2.0
export MODEL_TOP_P="1.0"                  # 默认: 1.0，范围 0.0-1.0
export MODEL_MAX_TOKENS="4096"            # 默认: 4096

# （可选）自定义输出目录
# 重要：相对路径将基于被分析的代码仓库，而非本项目目录
export OUTPUT_DIR=".wiki"                 # 相对路径（相对于被分析的代码仓库，默认值）
# 或
export OUTPUT_DIR="/absolute/path/to/output"  # 绝对路径
```

**使用第三方 API 示例**：

```bash
# DeepSeek API
export OPENAI_API_KEY="sk-xxx"
export OPENAI_BASE_URL="https://api.deepseek.com/v1"
export OPENAI_MODEL="deepseek-chat"

# Ollama 本地模型
export OPENAI_API_KEY="dummy-key"
export OPENAI_BASE_URL="http://localhost:11434/v1"
export OPENAI_MODEL="qwen2.5:14b"
```

#### 使用 Claude Agent SDK

```bash
# .env 文件或环境变量
export AGENT_SDK="claude"                 # 选择使用 Claude SDK
export ANTHROPIC_AUTH_TOKEN="your-auth-token"

# （可选）自定义模型名称和参数
export CLAUDE_MODEL="claude-sonnet-4-20250514"  # 可选，不指定则使用默认
export MODEL_TEMPERATURE="0.7"            # 默认: 0.7
export MODEL_TOP_P="1.0"                  # 默认: 1.0
export MODEL_MAX_TOKENS="4096"            # 默认: 4096
```

#### 配置参数说明

| 参数                     | 说明                                         | 默认值           |
| ------------------------ | -------------------------------------------- | ---------------- |
| `AGENT_SDK`            | 选择 Agent SDK：`"openai"` 或 `"claude"` | `"openai"`     |
| `OPENAI_API_KEY`       | OpenAI API 密钥（使用 OpenAI SDK 时必需）    | -                |
| `OPENAI_BASE_URL`      | 自定义 OpenAI API 地址（可选）               | 标准 OpenAI 地址 |
| `OPENAI_MODEL`         | OpenAI 模型名称                              | `"gpt-4o"`     |
| `ANTHROPIC_AUTH_TOKEN` | Claude API 令牌（使用 Claude SDK 时必需）    | -                |
| `CLAUDE_MODEL`         | Claude 模型名称（可选）                      | SDK 默认模型     |
| `MODEL_TEMPERATURE`    | 模型温度（0.0-2.0）                          | `0.7`          |
| `MODEL_TOP_P`          | Top-p 采样参数（0.0-1.0）                    | `1.0`          |
| `MODEL_MAX_TOKENS`     | 最大输出 token 数                            | `4096`         |
| `OUTPUT_DIR`           | 输出目录路径（相对路径基于被分析仓库）       | `".wiki"`      |

### 运行分析

```bash
# 分析指定代码仓库
python src/main.py /path/to/your/repo
```

### 查看结果

分析完成后，在**被分析代码仓库**的输出目录查看结果（默认为 `.wiki/`）：

```
/path/to/your/repo/.wiki/         # 输出目录（在被分析的代码仓库下）
├── prd/                          # 产品需求文档
│   ├── Index.md                  # 功能域导航索引
│   ├── 用户认证与授权.md         # 各功能域的详细PRD
│   ├── 订单管理.md
│   └── ...
└── debug/                        # 调试数据（JSON格式）
    ├── 01_structure_scan_final_*.json
    ├── 02_semantic_analysis_final_*.json
    └── ...
```

**示例**：

```bash
# 分析项目
python src/main.py /Users/username/my-project

# 结果将输出到
# /Users/username/my-project/.wiki/prd/
# /Users/username/my-project/.wiki/debug/
```

**建议**：将 `.wiki/` 添加到被分析项目的 `.gitignore` 文件中，避免提交分析结果到版本控制系统。

```bash
# 在被分析的项目根目录下
echo ".wiki/" >> .gitignore
```

**PRD 文档结构**：

```markdown
# [功能域名称]

## 1. 功能域概述
- 业务价值
- 核心能力
- 技术架构概览

## 2. 功能详细说明
- 各子功能的业务描述
- 用户场景
- 业务流程

## 3. 跨功能交互
- 与其他功能域的协作关系

## 4. 业务约束与限制
- 业务规则
- 边界条件
```

## 🛠️ 技术栈

| 技术                                           | 用途                               |
| ---------------------------------------------- | ---------------------------------- |
| **Claude Agent SDK / OpenAI Agents SDK** | AI 驱动的多 Agent 协作框架（可选） |
| **Tree-sitter**                          | 165+ 编程语言的统一 AST 解析       |
| **MCP**                                  | 工具调用的标准化协议               |
| **Python 3.11+**                         | 主要开发语言                       |

## 📁 项目结构

```
claude-deep-wiki/
├── src/
│   ├── wiki_agents/              # 三个分析 Agent
│   │   ├── structure_scanner_agent.py
│   │   ├── semantic_analyzer_agent.py
│   │   └── doc_generator_agent.py
│   ├── mcp_servers/              # MCP 工具服务器
│   │   └── code_analysis_server.py
│   ├── mcp_tools/                # 底层分析工具
│   │   ├── polyglot_parser.py   # Tree-sitter 解析器
│   │   ├── dependency_analyzer.py
│   │   ├── language_detector.py
│   │   └── universal_extractor.py
│   ├── utils/                    # 辅助工具
│   │   ├── agent_factory.py     # Agent 工厂（统一创建接口）
│   │   ├── unified_query_helper.py  # 统一查询助手
│   │   ├── claude_query_helper.py   # Claude 查询助手
│   │   ├── openai_query_helper.py   # OpenAI 查询助手
│   │   ├── batch_analyzer.py    # 批处理管理
│   │   ├── json_extractor.py    # JSON 提取
│   │   └── *_prompt_builder.py  # 提示词构建
│   ├── config.py                 # 配置文件（支持 .env）
│   └── main.py                   # 主入口
├── .env.example                  # 环境变量示例
├── requirements.txt              # Python 依赖
└── README.md                     # 项目文档
```

## 🎓 核心设计思想

### 防止 AI 幻觉

1. **分阶段处理**：每个阶段独立验证，避免错误累积
2. **工具驱动**：AI 通过工具获取真实数据，而非凭空想象
3. **智能重试**：自动检测 JSON 解析错误、模块遗漏等问题，最多重试 3 次
4. **质量检查**：自动验证输出中是否包含不合规内容（如技术术语）

### 鲁棒性设计

- **统一抽象层**：
  - `AgentFactory`：统一 Agent 创建接口，自动根据配置选择 SDK
  - `UnifiedQueryHelper`：统一查询接口，屏蔽 SDK 差异
  - SDK 特定实现：`ClaudeQueryHelper` 和 `OpenAIQueryHelper`
- **自动错误恢复**：
  - JSON 语法错误：自动重试，给 AI 第二次机会
  - 模块分组遗漏：验证器检测后触发重试，确保完整性
  - 字段缺失：验证器实时检查，避免后续流程失败
- **详细日志**：记录每次重试的原因，便于问题排查
- **灵活部署**：支持 OpenAI 兼容的第三方 API（DeepSeek、Ollama 等）

### Session/Thread 管理策略

不同 SDK 的会话管理差异已被统一抽象：

- **Claude SDK**：使用 session_id 字符串标识会话
- **OpenAI SDK**：使用 Thread 对象管理会话上下文

Agent 层面的策略：

- **StructureScannerAgent**：每个子阶段独立会话（显式传递数据）
- **SemanticAnalyzerAgent**：同一模块共享会话（保持上下文理解）
- **DocGeneratorAgent**：按功能域独立会话（避免混淆）

### 批处理优化

- Token 估算：根据文件内容预估 token 消耗
- 内聚性分组：将相关文件分到同一批次
- 动态调整：根据实际响应调整批次大小

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 License

[MIT License](LICENSE)

---

**⭐ 如果这个项目对你有帮助，请给个 Star！**
