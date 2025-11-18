"""
全局配置文件
"""

from pathlib import Path
import os
from dotenv import load_dotenv

# 加载 .env 文件（如果存在）
# 优先级：环境变量 > .env 文件 > 默认值
dotenv_path = Path(__file__).parent.parent / '.env'
if dotenv_path.exists():
    load_dotenv(dotenv_path)

# ============================================================================
# 目录配置
# ============================================================================

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

# 输出目录配置
# 注意：这里只是定义输出目录的相对路径名称，实际路径将在运行时动态设置
# - 如果 OUTPUT_DIR 环境变量是绝对路径，则使用该绝对路径
# - 如果 OUTPUT_DIR 环境变量是相对路径（或未设置），则相对于被分析的代码仓库
# 默认值: ".wiki"（会在被分析的代码仓库下创建 .wiki 目录）
OUTPUT_DIR_NAME = os.environ.get("OUTPUT_DIR", ".wiki")

# 运行时会被设置的全局变量（由 set_output_dir() 函数设置）
OUTPUT_DIR = None
DEBUG_DIR = None
DEFAULT_OUTPUT_FILE = None


# ============================================================================
# Agent 配置
# ============================================================================

# 最大对话轮次
MAX_TURNS = 100

# 默认扫描深度
DEFAULT_SCAN_DEPTH = 5

# 文件大小限制（MB）
MAX_FILE_SIZE_MB = 10.0


# ============================================================================
# 批处理配置
# ============================================================================

# 每批次最大token数（为Claude 200K上下文留安全边际）
BATCH_MAX_TOKENS = 150000

# Token估算比例（保守估计：3字符=1token）
TOKENS_PER_CHAR = 1 / 3.0

# 为提示词预留的token空间
PROMPT_RESERVED_TOKENS = 20000


# ============================================================================
# API 配置
# ============================================================================

# Agent SDK 选择（从环境变量读取，可选值: "claude" 或 "openai"）
# 默认: "openai"
AGENT_SDK = os.environ.get("AGENT_SDK", "openai").lower()

# === Claude Agent SDK 配置 ===
# Anthropic API Token（从环境变量读取）
ANTHROPIC_AUTH_TOKEN = os.environ.get("ANTHROPIC_AUTH_TOKEN")

# Claude 默认模型
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", None)  # None 表示使用 SDK 默认模型

# === OpenAI Agents SDK 配置 ===
# OpenAI API Key（从环境变量读取）
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# OpenAI API Base URL（从环境变量读取，可选）
# 用于支持自定义 API 端点（如 Azure OpenAI、代理服务等）
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL")  # None 表示使用默认地址

# OpenAI 默认模型（可通过环境变量自定义）
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o")

# === 统一模型配置（两个 SDK 都适用）===
# 根据选择的 SDK 设置默认模型
DEFAULT_MODEL = CLAUDE_MODEL if AGENT_SDK == "claude" else OPENAI_MODEL

# 模型参数（可通过环境变量自定义）
MODEL_TEMPERATURE = float(os.environ.get("MODEL_TEMPERATURE", "0.7"))  # 温度参数，控制随机性
MODEL_TOP_P = float(os.environ.get("MODEL_TOP_P", "1.0"))  # Top-p 采样参数
MODEL_MAX_TOKENS = int(os.environ.get("MODEL_MAX_TOKENS", "4096"))  # 最大生成 token 数


# ============================================================================
# 日志配置
# ============================================================================

# 日志级别
LOG_LEVEL = "INFO"

# 是否输出详细日志
VERBOSE = False

# 是否启用调试模式
DEBUG = False


# ============================================================================
# 文件过滤配置
# ============================================================================

# 默认排除的目录
DEFAULT_EXCLUDE_DIRS = {
    # Version Control
    '.git', '.svn', '.hg', '.bzr',

    # Dependencies
    'node_modules', 'vendor', 'bower_components',

    # Python
    '__pycache__', '.pytest_cache', '.mypy_cache',
    'venv', '.venv', 'env', '.env', 'virtualenv',
    '*.egg-info', 'dist', 'build', '.tox',

    # Build outputs
    'target', 'out', 'output', 'bin', 'obj',

    # IDE
    '.idea', '.vscode', '.vs',

    # Cache
    '.cache', '.npm', '.yarn', '.gradle',

    # Logs
    'logs',

    # Temporary
    'tmp', 'temp', '.tmp',
}

# 默认排除的文件模式
DEFAULT_EXCLUDE_PATTERNS = {
    '*.pyc', '*.pyo', '*.pyd',
    '*.so', '*.dylib', '*.dll',
    '*.class', '*.jar',
    '*.o', '*.a',
    '*.min.js', '*.min.css',
    '*.map',
    '*.lock', 'package-lock.json', 'yarn.lock',
    '.DS_Store', 'Thumbs.db',
}


# ============================================================================
# 工具函数
# ============================================================================

def set_output_dir(repo_path: str):
    """
    设置输出目录（基于被分析的代码仓库路径）

    Args:
        repo_path: 被分析的代码仓库路径
    """
    global OUTPUT_DIR, DEBUG_DIR, DEFAULT_OUTPUT_FILE

    repo_path = Path(repo_path).resolve()

    # 判断 OUTPUT_DIR_NAME 是绝对路径还是相对路径
    output_path = Path(OUTPUT_DIR_NAME)
    if output_path.is_absolute():
        # 绝对路径，直接使用
        OUTPUT_DIR = output_path
    else:
        # 相对路径，相对于被分析的代码仓库
        OUTPUT_DIR = repo_path / OUTPUT_DIR_NAME

    # 设置派生目录
    DEBUG_DIR = OUTPUT_DIR / "debug"
    DEFAULT_OUTPUT_FILE = OUTPUT_DIR / "business_modules.md"


def ensure_output_dir():
    """确保输出目录存在"""
    if OUTPUT_DIR is None:
        raise RuntimeError("OUTPUT_DIR 未初始化，请先调用 set_output_dir()")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def ensure_debug_dir():
    """确保 debug 目录存在"""
    if DEBUG_DIR is None:
        raise RuntimeError("DEBUG_DIR 未初始化，请先调用 set_output_dir()")
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)


def get_config_summary() -> dict:
    """获取配置摘要"""
    return {
        "project_root": str(PROJECT_ROOT),
        "output_dir": str(OUTPUT_DIR) if OUTPUT_DIR else "未初始化",
        "debug_dir": str(DEBUG_DIR) if DEBUG_DIR else "未初始化",
        "max_turns": MAX_TURNS,
        "max_file_size_mb": MAX_FILE_SIZE_MB,
        "has_api_key": bool(OPENAI_API_KEY),
        "log_level": LOG_LEVEL,
        "verbose": VERBOSE,
        "debug": DEBUG,
    }


# ============================================================================
# 初始化
# ============================================================================

# 注意：输出目录不在模块加载时创建，而是在调用 set_output_dir() 后按需创建

