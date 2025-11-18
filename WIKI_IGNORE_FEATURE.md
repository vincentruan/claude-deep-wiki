# Wiki Ignore Feature Documentation

## 概述

Wiki Ignore 功能允许用户通过创建自定义的忽略文件来控制代码扫描时需要排除的文件和目录。这个功能的设计参考了 `.gitignore` 的使用方式，但专门用于 DeepWiki 的代码分析场景。

## 功能特性

### 1. 多种文件名支持

支持以下三种文件名（按优先级排序）：

1. `.wiki_ignore` （推荐）
2. `.wikiignore`
3. `.wiki-ignore`

系统会自动查找这些文件，优先使用 `.wiki_ignore`。

### 2. 兼容 .gitignore 语法

完全兼容 `.gitignore` 的所有语法规则：

- 支持通配符（`*`, `?`, `**`）
- 支持否定模式（`!pattern`）
- 支持目录匹配（`dir/`）
- 支持注释（`# comment`）

### 3. 优先级规则

文件和目录的排除优先级如下（从高到低）：

1. **默认排除列表**：如 `.git`、`node_modules`、`__pycache__` 等
2. **Wiki Ignore 规则**：用户自定义的 wiki ignore 文件
3. **.gitignore 规则**：项目的 .gitignore 文件

## 使用方法

### 创建 Wiki Ignore 文件

在被分析的代码仓库根目录下创建文件：

```bash
# 在项目根目录
touch .wiki_ignore
```

### 编写规则

```bash
# .wiki_ignore 示例

# 忽略测试目录
tests/
test_*/

# 忽略特定文件类型
*.test.js
*.spec.ts

# 忽略临时文件
*.tmp
*.cache
temp/

# 忽略文档草稿
docs/drafts/
*.draft.md
```

### 运行分析

创建 wiki ignore 文件后，正常运行分析即可：

```bash
python src/main.py /path/to/your/repo
```

系统会自动检测并应用 wiki ignore 规则。

## 实现细节

### 文件结构

主要修改的文件：

- `src/mcp_tools/file_filter.py` - 核心过滤逻辑
- `src/mcp_servers/code_analysis_server.py` - MCP 工具接口

### 核心方法

#### FileFilter 类

```python
class FileFilter:
    def __init__(
        self,
        exclude_dirs: Optional[Set[str]] = None,
        exclude_patterns: Optional[Set[str]] = None,
        gitignore_path: Optional[str | Path] = None,
        wikiignore_path: Optional[str | Path] = None,  # 新增
        max_file_size_mb: float = MAX_FILE_SIZE_MB
    ):
        # ...
```

#### 主要新增方法

1. `_load_wikiignore(wikiignore_path)` - 加载 wiki ignore 文件
2. `_find_wikiignore_file(directory)` - 自动查找 wiki ignore 文件

#### 更新的方法

1. `should_exclude_dir(dir_path)` - 增加 wiki ignore 规则检查
2. `should_exclude_file(file_path)` - 增加 wiki ignore 规则检查

### API 更新

MCP 工具 `scan_repository_structure` 新增参数：

```python
def scan_repository_structure(
    repo_path: str,
    max_depth: int = 5,
    include_extensions: Optional[List[str]] = None,
    exclude_patterns: Optional[List[str]] = None,
    use_wikiignore: bool = True  # 新增，默认启用
) -> Dict[str, Any]:
```

## 使用场景

### 场景 1：排除测试代码

当你只想分析业务代码，不需要分析测试代码时：

```bash
# .wiki_ignore
tests/
*_test.py
*.test.js
*.spec.ts
```

### 场景 2：排除文档和示例

当你想专注于代码实现，忽略文档和示例：

```bash
# .wiki_ignore
docs/
examples/
samples/
*.md
```

### 场景 3：排除实验性代码

当你有实验性或废弃的代码目录：

```bash
# .wiki_ignore
experimental/
deprecated/
legacy/
prototype/
```

### 场景 4：排除生成的代码

当项目包含自动生成的代码：

```bash
# .wiki_ignore
*_generated.py
*.generated.ts
auto_generated/
codegen/
```

## 最佳实践

1. **明确目标**：在创建 wiki ignore 文件前，先明确分析的目标和范围
2. **渐进式添加**：先运行一次分析，根据结果逐步添加需要排除的内容
3. **保持简洁**：只添加必要的排除规则，避免过度过滤
4. **添加注释**：在 wiki ignore 文件中添加注释，说明排除的原因
5. **版本控制**：建议将 `.wiki_ignore` 文件纳入版本控制，团队共享

## 技术依赖

- **pathspec** (>= 0.12.1)：用于解析和匹配 gitignore 风格的模式
- 如果 pathspec 未安装，wiki ignore 功能会自动禁用，但不影响基本扫描功能

## 示例文件

项目提供了一个示例文件 `.wiki_ignore.example`，包含常见的排除模式。可以复制并根据需要修改：

```bash
cp .wiki_ignore.example .wiki_ignore
# 然后编辑 .wiki_ignore
```

## 故障排查

### Wiki ignore 未生效

检查以下几点：

1. 文件名是否正确（`.wiki_ignore`、`.wikiignore` 或 `.wiki-ignore`）
2. 文件是否在被分析仓库的根目录
3. `pathspec` 库是否已安装
4. 检查日志输出，确认文件是否被加载

### 规则语法错误

- 参考 `.gitignore` 语法文档
- 使用 `#` 添加注释
- 目录必须以 `/` 结尾
- 使用 `!` 可以否定之前的规则

## 未来改进

可能的扩展方向：

1. 支持在配置文件中指定 wiki ignore 文件路径
2. 支持多个 wiki ignore 文件（类似 .gitignore 的层级机制）
3. 提供 wiki ignore 规则验证工具
4. 增加交互式规则配置向导

## 参考资料

- [gitignore 文档](https://git-scm.com/docs/gitignore)
- [pathspec 库文档](https://github.com/cpburnz/python-pathspec)
