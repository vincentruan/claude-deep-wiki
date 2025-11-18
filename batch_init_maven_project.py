#!/usr/bin/env python3
"""
Maven 项目批量分析工具

该脚本用于批量分析包含 pom.xml 的 Maven 管理的 Java 项目。
支持包含多个 Maven 父工程的复杂项目结构。

执行策略：
1. 自动识别目录下的所有 Maven 父工程
2. 对每个父工程，按照 子模块 -> 父模块 的顺序依次分析
3. 优先完成一个父工程的所有模块，再处理下一个父工程

功能特性：
1. 自动扫描目录树，找到所有包含 pom.xml 的模块
2. 智能识别并分组多个独立的 Maven 父工程
3. 解析 Maven 依赖关系，构建模块依赖图
4. 使用拓扑排序确定最优分析顺序（处理复杂依赖关系）
5. 详细的日志记录，包含父工程分组和执行进度
6. 按父工程分组的结果汇总统计
"""

import asyncio
import logging
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple
import subprocess


# 配置日志
LOG_FILE = Path(__file__).parent / f"batch_maven_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# 配置日志格式
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


class MavenModule:
    """Maven 模块信息"""

    def __init__(self, path: Path, pom_path: Path):
        self.path = path
        self.pom_path = pom_path
        self.group_id: Optional[str] = None
        self.artifact_id: Optional[str] = None
        self.version: Optional[str] = None
        self.parent: Optional[Tuple[str, str, Optional[str]]] = None  # (groupId, artifactId, version)
        self.modules: List[str] = []  # 子模块相对路径
        self.dependencies: List[Tuple[str, str]] = []  # [(groupId, artifactId)]

    def __repr__(self):
        return f"MavenModule({self.artifact_id} at {self.path})"

    def get_coordinate(self) -> str:
        """获取 Maven 坐标标识"""
        return f"{self.group_id}:{self.artifact_id}:{self.version}"


class MavenModuleParser:
    """Maven 模块解析器"""

    # Maven POM 命名空间
    NAMESPACES = {
        'mvn': 'http://maven.apache.org/POM/4.0.0'
    }

    @staticmethod
    def find_all_pom_files(root_path: Path) -> List[Path]:
        """递归查找所有 pom.xml 文件"""
        pom_files = []

        # 排除常见的构建目录和隐藏目录
        exclude_dirs = {'target', 'build', '.git', '.svn', 'node_modules', '.idea'}

        for pom_path in root_path.rglob('pom.xml'):
            # 检查路径中是否包含排除的目录
            if any(excluded in pom_path.parts for excluded in exclude_dirs):
                continue
            pom_files.append(pom_path)

        logger.info(f"找到 {len(pom_files)} 个 pom.xml 文件")
        return pom_files

    @staticmethod
    def parse_pom(pom_path: Path) -> Optional[MavenModule]:
        """解析单个 pom.xml 文件"""
        try:
            tree = ET.parse(pom_path)
            root = tree.getroot()

            module = MavenModule(path=pom_path.parent, pom_path=pom_path)

            # 处理命名空间（可能有也可能没有）
            ns = {'mvn': root.tag.split('}')[0].strip('{')} if '}' in root.tag else {}

            def find_text(element, tag: str) -> Optional[str]:
                """查找元素文本（支持有无命名空间）"""
                if ns:
                    found = element.find(f"mvn:{tag}", ns)
                else:
                    found = element.find(tag)
                return found.text.strip() if found is not None and found.text else None

            # 解析基本信息
            module.group_id = find_text(root, 'groupId')
            module.artifact_id = find_text(root, 'artifactId')
            module.version = find_text(root, 'version')

            # 解析父模块信息
            parent_elem = root.find('mvn:parent', ns) if ns else root.find('parent')
            if parent_elem is not None:
                parent_group = find_text(parent_elem, 'groupId')
                parent_artifact = find_text(parent_elem, 'artifactId')
                parent_version = find_text(parent_elem, 'version')
                if parent_group and parent_artifact:
                    module.parent = (parent_group, parent_artifact, parent_version)

                # 如果当前模块的 groupId 或 version 未定义，继承父模块的
                if not module.group_id:
                    module.group_id = parent_group
                if not module.version:
                    module.version = parent_version

            # 解析子模块列表
            modules_elem = root.find('mvn:modules', ns) if ns else root.find('modules')
            if modules_elem is not None:
                for module_elem in modules_elem.findall('mvn:module' if ns else 'module', ns):
                    if module_elem.text:
                        module.modules.append(module_elem.text.strip())

            # 解析依赖项
            dependencies_elem = root.find('mvn:dependencies', ns) if ns else root.find('dependencies')
            if dependencies_elem is not None:
                for dep_elem in dependencies_elem.findall('mvn:dependency' if ns else 'dependency', ns):
                    dep_group = find_text(dep_elem, 'groupId')
                    dep_artifact = find_text(dep_elem, 'artifactId')
                    if dep_group and dep_artifact:
                        module.dependencies.append((dep_group, dep_artifact))

            return module

        except Exception as e:
            logger.error(f"解析 {pom_path} 失败: {e}")
            return None

    @staticmethod
    def identify_parent_projects(modules: List[MavenModule]) -> Dict[str, List[MavenModule]]:
        """
        识别并分组父工程及其子模块

        返回: {parent_project_id: [modules_in_this_project]}
        """
        # 构建模块索引：(groupId, artifactId) -> MavenModule
        module_index: Dict[Tuple[str, str], MavenModule] = {}
        for module in modules:
            if module.group_id and module.artifact_id:
                module_index[(module.group_id, module.artifact_id)] = module

        # 识别顶级父工程（没有父模块，或者父模块不在当前解析的模块中）
        root_parents = []
        for module in modules:
            if not module.parent:
                # 没有父模块，是根项目
                root_parents.append(module)
            else:
                parent_key = (module.parent[0], module.parent[1])
                if parent_key not in module_index:
                    # 父模块不在当前解析的模块中，说明当前模块是本次分析的顶级项目
                    root_parents.append(module)

        # 为每个模块找到其所属的根父工程
        def find_root_parent(module: MavenModule) -> Optional[MavenModule]:
            """递归查找模块的根父工程"""
            if not module.parent:
                return module

            parent_key = (module.parent[0], module.parent[1])
            if parent_key not in module_index:
                # 父模块不在当前解析列表中，当前模块就是根
                return module

            parent_module = module_index[parent_key]
            return find_root_parent(parent_module)

        # 按根父工程分组
        project_groups: Dict[str, List[MavenModule]] = {}

        for module in modules:
            root = find_root_parent(module)
            if root:
                root_key = f"{root.group_id}:{root.artifact_id}"
                if root_key not in project_groups:
                    project_groups[root_key] = []
                project_groups[root_key].append(module)

        # 如果没有识别到任何分组，将所有模块归为一组
        if not project_groups:
            project_groups['default'] = modules

        logger.info(f"\n识别到 {len(project_groups)} 个独立的 Maven 父工程")
        for project_id, project_modules in project_groups.items():
            logger.info(f"  - {project_id}: {len(project_modules)} 个模块")

        return project_groups

    @staticmethod
    def build_dependency_order(modules: List[MavenModule]) -> List[MavenModule]:
        """
        构建模块分析顺序：子模块 -> 父模块

        使用拓扑排序确定执行顺序：
        1. 子模块依赖父模块，所以子模块应该先执行
        2. 有依赖关系的模块，被依赖的模块先执行
        """
        if not modules:
            return []

        # 构建模块索引：(groupId, artifactId) -> MavenModule
        module_index: Dict[Tuple[str, str], MavenModule] = {}
        for module in modules:
            if module.group_id and module.artifact_id:
                module_index[(module.group_id, module.artifact_id)] = module

        # 构建依赖图：module -> 依赖它的模块列表（反向依赖）
        dependency_graph: Dict[MavenModule, Set[MavenModule]] = {m: set() for m in modules}
        in_degree: Dict[MavenModule, int] = {m: 0 for m in modules}

        for module in modules:
            # 1. 处理父模块关系（子模块依赖父模块）
            if module.parent:
                parent_key = (module.parent[0], module.parent[1])
                if parent_key in module_index:
                    parent_module = module_index[parent_key]
                    # 父模块依赖于子模块的完成（反向依赖）
                    dependency_graph[module].add(parent_module)
                    in_degree[parent_module] += 1

            # 2. 处理模块依赖关系
            for dep_group, dep_artifact in module.dependencies:
                dep_key = (dep_group, dep_artifact)
                if dep_key in module_index:
                    dep_module = module_index[dep_key]
                    # 当前模块依赖于 dep_module
                    dependency_graph[dep_module].add(module)
                    in_degree[module] += 1

        # 拓扑排序（Kahn's algorithm）
        queue = [m for m in modules if in_degree[m] == 0]
        sorted_modules = []

        while queue:
            # 按路径排序，确保同级模块有稳定的顺序
            queue.sort(key=lambda m: str(m.path))
            current = queue.pop(0)
            sorted_modules.append(current)

            # 减少依赖当前模块的其他模块的入度
            for dependent in dependency_graph[current]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        # 检查是否有循环依赖
        if len(sorted_modules) != len(modules):
            logger.warning(f"检测到循环依赖！已排序 {len(sorted_modules)}/{len(modules)} 个模块")
            # 将剩余模块添加到末尾
            remaining = [m for m in modules if m not in sorted_modules]
            sorted_modules.extend(remaining)

        return sorted_modules


class BatchMavenAnalyzer:
    """批量 Maven 项目分析器"""

    def __init__(self, root_path: Path):
        self.root_path = root_path
        self.parser = MavenModuleParser()
        self.results: Dict[str, Dict] = {}

    async def analyze_all(self) -> Dict[str, Dict]:
        """执行批量分析"""
        logger.info(f"开始批量分析 Maven 项目: {self.root_path}")
        logger.info("="*80)

        # 1. 查找所有 pom.xml 文件
        pom_files = self.parser.find_all_pom_files(self.root_path)
        if not pom_files:
            logger.warning("未找到任何 pom.xml 文件")
            return {}

        # 2. 解析所有模块
        modules = []
        for pom_path in pom_files:
            module = self.parser.parse_pom(pom_path)
            if module:
                modules.append(module)
                logger.info(f"  解析模块: {module.artifact_id} ({module.path})")

        logger.info(f"\n成功解析 {len(modules)} 个 Maven 模块")
        logger.info("="*80)

        # 3. 按父工程分组
        project_groups = self.parser.identify_parent_projects(modules)

        # 4. 对每个父工程内的模块进行排序并执行分析
        global_counter = 0
        total_modules = len(modules)

        for project_idx, (project_id, project_modules) in enumerate(project_groups.items(), 1):
            logger.info("\n" + "="*80)
            logger.info(f"父工程 [{project_idx}/{len(project_groups)}]: {project_id}")
            logger.info(f"包含 {len(project_modules)} 个模块")
            logger.info("="*80)

            # 对当前父工程的模块进行拓扑排序（子模块 -> 父模块）
            sorted_project_modules = self.parser.build_dependency_order(project_modules)

            logger.info(f"\n[{project_id}] 分析顺序（子模块 -> 父模块）：")
            for idx, module in enumerate(sorted_project_modules, 1):
                parent_info = ""
                if module.parent:
                    parent_info = f" (parent: {module.parent[1]})"
                logger.info(f"  {idx}. {module.artifact_id}{parent_info}")
            logger.info("-"*80)

            # 5. 按顺序执行分析
            for module_idx, module in enumerate(sorted_project_modules, 1):
                global_counter += 1
                logger.info(f"\n[总进度: {global_counter}/{total_modules}] [父工程: {project_id}] [{module_idx}/{len(sorted_project_modules)}]")
                logger.info(f"开始分析: {module.artifact_id}")
                logger.info(f"  路径: {module.path}")
                logger.info(f"  坐标: {module.get_coordinate()}")

                try:
                    result = await self.analyze_single_module(module)
                    self.results[str(module.path)] = {
                        'module': module.artifact_id,
                        'coordinate': module.get_coordinate(),
                        'parent_project': project_id,
                        'status': 'success' if result else 'failed',
                        'result': result
                    }

                    if result:
                        logger.info(f"  ✅ 分析成功")
                    else:
                        logger.error(f"  ❌ 分析失败")

                except Exception as e:
                    logger.error(f"  ❌ 分析异常: {e}", exc_info=True)
                    self.results[str(module.path)] = {
                        'module': module.artifact_id,
                        'coordinate': module.get_coordinate(),
                        'parent_project': project_id,
                        'status': 'error',
                        'error': str(e)
                    }

                logger.info("-"*80)

            logger.info(f"\n✅ 父工程 [{project_id}] 的所有模块分析完成")
            logger.info("="*80)

        # 6. 输出汇总结果
        self.print_summary()

        return self.results

    async def analyze_single_module(self, module: MavenModule) -> bool:
        """
        分析单个 Maven 模块

        调用 main.py 对该模块进行深度分析
        """
        try:
            # 获取当前脚本所在目录的 src/main.py
            main_script = Path(__file__).parent / "src" / "main.py"

            if not main_script.exists():
                logger.error(f"  找不到分析脚本: {main_script}")
                return False

            # 构建命令
            cmd = [
                sys.executable,
                str(main_script),
                str(module.path)
            ]

            logger.info(f"  执行命令: {' '.join(cmd)}")

            # 执行分析（使用 subprocess 而非 asyncio 导入 main，避免模块冲突）
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            # 记录输出
            if stdout:
                logger.info(f"  标准输出:\n{stdout.decode('utf-8', errors='ignore')}")
            if stderr:
                logger.warning(f"  错误输出:\n{stderr.decode('utf-8', errors='ignore')}")

            # 检查返回码
            if process.returncode == 0:
                return True
            else:
                logger.error(f"  进程返回码: {process.returncode}")
                return False

        except Exception as e:
            logger.error(f"  执行分析时出错: {e}", exc_info=True)
            return False

    def print_summary(self):
        """打印分析结果汇总"""
        logger.info("\n" + "="*80)
        logger.info("批量分析完成 - 结果汇总")
        logger.info("="*80)

        success_count = sum(1 for r in self.results.values() if r['status'] == 'success')
        failed_count = sum(1 for r in self.results.values() if r['status'] == 'failed')
        error_count = sum(1 for r in self.results.values() if r['status'] == 'error')

        logger.info(f"\n总体统计:")
        logger.info(f"  总计: {len(self.results)} 个模块")
        logger.info(f"  ✅ 成功: {success_count}")
        logger.info(f"  ❌ 失败: {failed_count}")
        logger.info(f"  ⚠️  异常: {error_count}")

        # 按父工程分组统计
        project_stats: Dict[str, Dict[str, int]] = {}
        for result in self.results.values():
            project_id = result.get('parent_project', 'unknown')
            if project_id not in project_stats:
                project_stats[project_id] = {'success': 0, 'failed': 0, 'error': 0, 'total': 0}

            project_stats[project_id]['total'] += 1
            if result['status'] == 'success':
                project_stats[project_id]['success'] += 1
            elif result['status'] == 'failed':
                project_stats[project_id]['failed'] += 1
            elif result['status'] == 'error':
                project_stats[project_id]['error'] += 1

        logger.info(f"\n各父工程统计:")
        for project_id, stats in project_stats.items():
            logger.info(f"\n  📦 {project_id}")
            logger.info(f"     总计: {stats['total']} | ✅ {stats['success']} | ❌ {stats['failed']} | ⚠️  {stats['error']}")

        if failed_count > 0 or error_count > 0:
            logger.info("\n失败/异常的模块详情：")
            for path, result in self.results.items():
                if result['status'] in ['failed', 'error']:
                    logger.info(f"  - [{result.get('parent_project', 'unknown')}] {result['module']}")
                    logger.info(f"    路径: {path}")
                    if 'error' in result:
                        logger.info(f"    错误: {result['error']}")

        logger.info("\n" + "="*80)
        logger.info(f"详细日志已保存至: {LOG_FILE}")
        logger.info("="*80)


async def main():
    """主入口"""
    import argparse

    parser = argparse.ArgumentParser(
        description="批量分析 Maven 项目（按照子模块 -> 父模块的顺序）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 分析当前目录下的所有 Maven 模块
  python batch_init_maven_project.py .

  # 分析指定目录
  python batch_init_maven_project.py /path/to/maven/project

  # 查看详细日志
  tail -f batch_maven_analysis_*.log
        """
    )

    parser.add_argument(
        'root_path',
        type=Path,
        help='Maven 项目根目录路径（将递归查找所有 pom.xml）'
    )

    args = parser.parse_args()

    # 检查路径是否存在
    if not args.root_path.exists():
        logger.error(f"路径不存在: {args.root_path}")
        sys.exit(1)

    if not args.root_path.is_dir():
        logger.error(f"路径不是目录: {args.root_path}")
        sys.exit(1)

    # 执行批量分析
    analyzer = BatchMavenAnalyzer(args.root_path)

    try:
        await analyzer.analyze_all()
        logger.info("\n✅ 所有分析任务已完成")
    except KeyboardInterrupt:
        logger.warning("\n⚠️  用户中断")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n❌ 批量分析失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
