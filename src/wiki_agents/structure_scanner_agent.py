"""
Structure Scanner Agent - 结构扫描 Agent

专注于代码仓库结构梳理，不做深度语义理解。

职责:
1. 扫描仓库完整结构
2. 识别模块层次（一级/二级/三级）
3. 分析模块依赖关系（基于导入导出）
4. 智能判断模块分层（core/business/utils）
5. 生成文件到模块的映射
"""

import sys
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_servers.code_analysis_server import create_code_analysis_mcp_server
from config import AGENT_SDK
from utils.structure_prompt_builder import StructurePromptBuilder
from utils.json_extractor import JSONExtractor
from utils.unified_query_helper import UnifiedQueryHelper
from utils.agent_factory import AgentFactory

logger = None  # 简化日志


class StructureScannerAgent:
    """结构扫描 Agent - 专注于模块结构梳理"""

    def __init__(self, debug_helper):
        """
        初始化结构扫描 Agent

        Args:
            debug_helper: DebugHelper 实例
        """
        self.debug_helper = debug_helper
        self.last_response = ""  # 记录最后一次响应，用于调试保存

        # 创建 MCP Server
        self._mcp_server = create_code_analysis_mcp_server()

        # 使用工厂创建 Agent（根据配置自动选择 Claude 或 OpenAI）
        self.client, self.openai_client, self._threads = AgentFactory.create_client(
            name="StructureScanner",
            instructions="你是代码仓库结构分析专家，擅长识别项目模块划分和依赖关系。",
            mcp_server=self._mcp_server
        )

        self._connected = False  # 连接状态（仅 Claude 需要）

    async def scan_repository(self, repo_path: str) -> Dict[str, Any]:
        """
        完整扫描仓库结构（3阶段设计）

        阶段1: 结构扫描与模块识别（1次工具调用）
        阶段2: 依赖分析（50次工具调用）
        阶段3: 综合分析（0次工具调用）

        Args:
            repo_path: 仓库根目录路径

        Returns:
            {
                "project_info": {...},
                "module_hierarchy": {...},
                "dependency_graph": {...},
                "file_module_mapping": {...}
            }
        """
        # 确保已连接（仅 Claude 需要）
        if not self._connected:
            await AgentFactory.connect_client(self.client)
            self._connected = True

        # 尝试加载完整缓存
        cached_final = self.debug_helper.load_cached_data("01_structure_scan_final")
        if cached_final:
            return cached_final

        # === 阶段1: 结构扫描与模块识别 ===
        print("  → 阶段 1/3: 扫描项目结构...")
        cached_overview = self.debug_helper.load_cached_data("01_structure_overview")
        if cached_overview:
            structure_overview = cached_overview
        else:
            structure_overview = await self._scan_and_identify_modules(repo_path)
            self.debug_helper.save_stage_data(
                "01_structure_overview",
                self.last_response,
                structure_overview
            )

        modules_count = len(structure_overview.get('modules', []))
        print(f"     识别到 {modules_count} 个模块")

        # === 阶段2: 依赖分析 ===
        print("  → 阶段 2/3: 分析文件依赖...")
        cached_deps = self.debug_helper.load_cached_data("01_structure_dependencies")
        if cached_deps:
            dependencies = cached_deps
        else:
            dependencies = await self._analyze_file_dependencies(
                structure_overview, repo_path
            )
            self.debug_helper.save_stage_data(
                "01_structure_dependencies",
                self.last_response,
                dependencies
            )

        deps_count = len(dependencies.get('file_dependencies', []))
        print(f"     分析了 {deps_count} 个关键文件")

        # === 阶段3: 综合分析 ===
        print("  → 阶段 3/3: 整合结构与分层...")
        final_structure = await self._finalize_structure(
            structure_overview, dependencies
        )

        # 保存最终结果
        self.debug_helper.save_stage_data(
            "01_structure_scan_final",
            self.last_response,
            final_structure
        )

        return final_structure

    async def _scan_and_identify_modules(self, repo_path: str) -> Dict[str, Any]:
        """
        阶段1: 结构扫描与模块识别

        工具调用: 1次 scan_repository_structure

        职责:
        - 扫描仓库结构
        - 识别所有业务功能模块
        - 选择关键文件（只有路径，不分析）
        - 初步判断模块分层
        - 列出所有相关文件

        Returns:
            {
                "project_info": {...},
                "modules": [
                    {
                        "name": "模块名",
                        "layer_guess": "business",
                        "responsibility": "简短描述",
                        "key_files_paths": ["path1", "path2"],
                        "all_files": [...]
                    }
                ]
            }
        """
        # 使用 PromptBuilder 构建提示词
        prompt = StructurePromptBuilder.build_scan_and_identify_prompt(repo_path)

        # Phase 1 使用独立session/thread
        # 原因：下一阶段会通过结构化数据传递输出，不需要对话历史

        # 使用统一查询助手（自动适配 Claude 或 OpenAI）
        response_text, overview = await UnifiedQueryHelper.query_with_json_retry(
            client=self.client,
            prompt=prompt,
            session_id=self._get_session_id("structure_scan_phase1"),
            max_attempts=3,
            validator=lambda r: bool(r and r.get('modules'))
        )

        self.last_response = response_text
        return overview

    async def _analyze_file_dependencies(
        self, structure_overview: Dict[str, Any], repo_path: str
    ) -> Dict[str, Any]:
        """
        阶段2: 依赖分析

        工具调用: 50次 extract_imports_and_exports

        职责:
        - 从阶段1结果中提取所有关键文件路径
        - 逐个分析关键文件
        - 提取 imports/exports
        - 不做复杂推理

        Returns:
            {
                "file_dependencies": [
                    {
                        "path": "src/module/main.js",
                        "imports": [...],
                        "exports": [...],
                        "language": "javascript",
                        "module": "模块名"
                    }
                ]
            }
        """
        modules = structure_overview.get('modules', [])

        # 收集所有关键文件
        all_key_files = []
        for module in modules:
            key_paths = module.get('key_files_paths', [])
            for path in key_paths:
                all_key_files.append({
                    'path': path,
                    'module': module.get('name', 'Unknown')
                })

        # 使用 PromptBuilder 构建提示词
        prompt = StructurePromptBuilder.build_file_dependencies_prompt(
            repo_path, all_key_files
        )

        # Phase 2 使用独立session/thread，避免Phase 1对话历史的冗余
        # 必要的信息已通过 all_key_files 参数显式传递

        # 使用统一查询助手
        response_text, dependencies = await UnifiedQueryHelper.query_with_json_retry(
            client=self.client,
            prompt=prompt,
            session_id=self._get_session_id("structure_scan_phase2"),
            max_attempts=3,
            validator=lambda r: bool(r and r.get('file_dependencies'))
        )

        self.last_response = response_text
        return dependencies

    async def _finalize_structure(
        self, structure_overview: Dict[str, Any], dependencies: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        阶段3: 综合分析

        工具调用: 0次（纯分析）

        职责:
        - 将依赖信息整合回模块
        - 基于真实依赖精确分层
        - 构建依赖图
        - 生成文件映射

        Returns:
            {
                "project_info": {...},
                "module_hierarchy": {...},
                "dependency_graph": {...},
                "file_module_mapping": {...}
            }
        """
        # 使用 PromptBuilder 构建提示词
        prompt = StructurePromptBuilder.build_finalize_structure_prompt(
            structure_overview, dependencies
        )

        # Phase 3 使用独立session/thread，避免前两阶段对话历史的冗余
        # Phase 1和2的输出已通过 structure_overview 和 dependencies 参数显式传递

        # 使用统一查询助手
        response_text, final_structure = await UnifiedQueryHelper.query_with_json_retry(
            client=self.client,
            prompt=prompt,
            session_id=self._get_session_id("structure_scan_phase3"),
            max_attempts=3,
            validator=lambda r: bool(r and r.get('module_hierarchy'))
        )

        self.last_response = response_text
        return final_structure

    def _get_session_id(self, session_key: str) -> Optional[str]:
        """
        获取会话ID（Claude 或 OpenAI）

        Args:
            session_key: 会话标识符

        Returns:
            Claude: 返回 session_key
            OpenAI: 返回 threads.get(session_key) 或 None
        """
        return AgentFactory.get_session_id(session_key, self._threads)

    async def disconnect(self):
        """断开连接并清理资源"""
        if self._connected:
            await AgentFactory.disconnect_client(self.client, self.openai_client)
            self._connected = False


# ============================================================================
# 独立测试接口
# ============================================================================

async def test_scanner():
    """独立测试结构扫描 Agent"""
    import asyncio

    # 添加路径以导入其他模块
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from utils.debug_helper import DebugHelper

    # 测试参数
    repo_path = "/Users/huli/svn_work/xiaoyue_sdk_hippy"  # 修改为你的测试仓库路径

    print("=" * 60)
    print("🧪 结构扫描 Agent 独立测试")
    print("=" * 60)

    # 创建 Debug Helper
    debug_helper = DebugHelper(enabled=True, verbose=True)

    # 创建扫描 Agent（Agent 内部会创建 client）
    scanner = StructureScannerAgent(debug_helper, verbose=True)

    try:
        # 执行扫描（Agent 会自动连接和设置权限）
        structure = await scanner.scan_repository(repo_path)

        # 输出结果摘要
        print("\n" + "=" * 60)
        print("📊 扫描结果摘要")
        print("=" * 60)

        project_info = structure.get('project_info', {})
        print(f"\n项目名称: {project_info.get('name')}")
        print(f"主要语言: {project_info.get('primary_language')}")
        print(f"文件总数: {project_info.get('total_files')}")

        modules = structure.get('module_hierarchy', {}).get('modules', [])
        print(f"\n识别模块数: {len(modules)}")

        for i, module in enumerate(modules[:5], 1):  # 只显示前5个
            print(f"\n{i}. {module.get('name')}")
            print(f"   层次: {module.get('layer')}")
            print(f"   职责: {module.get('responsibility')}")
            print(f"   文件数: {len(module.get('all_files', []))}")
            print(f"   关键文件: {len(module.get('key_files', []))}")

        if len(modules) > 5:
            print(f"\n   ... 还有 {len(modules) - 5} 个模块")

        dependency_graph = structure.get('dependency_graph', {})
        edges = dependency_graph.get('edges', [])
        print(f"\n依赖关系: {len(edges)} 条")

        print("\n✅ 测试完成！详细结果已保存到 output/debug/ 目录")

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await scanner.disconnect()


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_scanner())

