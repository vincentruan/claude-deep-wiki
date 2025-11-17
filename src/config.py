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

# 输出目录
# 支持从环境变量读取:
# - 如果提供绝对路径，直接使用
# - 如果提供相对路径，相对于项目根目录
# - 如果未设置，使用默认路径 PROJECT_ROOT/output
_output_dir_str = os.environ.get("OUTPUT_DIR", "output")
_output_path = Path(_output_dir_str)
OUTPUT_DIR = _output_path if _output_path.is_absolute() else PROJECT_ROOT / _output_dir_str

# Debug 输出目录
DEBUG_DIR = OUTPUT_DIR / "debug"

# 默认输出文件
DEFAULT_OUTPUT_FILE = OUTPUT_DIR / "business_modules.md"


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

def ensure_output_dir():
    """确保输出目录存在"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def ensure_debug_dir():
    """确保 debug 目录存在"""
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)


def get_config_summary() -> dict:
    """获取配置摘要"""
    return {
        "project_root": str(PROJECT_ROOT),
        "output_dir": str(OUTPUT_DIR),
        "debug_dir": str(DEBUG_DIR),
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

# 确保输出目录存在
ensure_output_dir()

