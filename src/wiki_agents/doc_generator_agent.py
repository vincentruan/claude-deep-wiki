"""
文档生成 Agent
负责将语义分析结果转换为产品需求文档（PRD）
"""

import os
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.prd_prompt_builder import PRDPromptBuilder
from utils.json_extractor import JSONExtractor
from utils.debug_helper import DebugHelper
from utils.unified_query_helper import UnifiedQueryHelper
from utils.agent_factory import AgentFactory
import config


class DocGeneratorAgent:
    """文档生成代理，将技术分析转换为产品文档"""

    def __init__(self, debug_helper: DebugHelper):
        """
        初始化文档生成代理

        Args:
            debug_helper: 调试助手
        """
        self.debug_helper = debug_helper
        self.prd_dir = os.path.join(config.OUTPUT_DIR, "prd")

        # 使用工厂创建 Agent（根据配置自动选择 Claude 或 OpenAI）
        # 文档生成不需要 MCP 工具
        self.client, self.openai_client, self._threads = AgentFactory.create_client(
            name="DocGenerator",
            instructions="你是一位资深的产品经理，擅长将技术分析转换为产品需求文档。",
            mcp_server=None,
            tools=[]
        )

        self._connected = False  # 连接状态（仅 Claude 需要）

        # 创建输出目录
        os.makedirs(self.prd_dir, exist_ok=True)

    async def generate_prd_documents(
        self,
        semantic_result: Dict[str, Any],
        repo_path: str
    ) -> Dict[str, Any]:
        """
        生成产品需求文档

        Args:
            semantic_result: 语义分析结果
            repo_path: 仓库路径

        Returns:
            生成结果
        """
        # 确保已连接（仅 Claude 需要）
        if not self._connected:
            await AgentFactory.connect_client(self.client)
            self._connected = True

        modules_analysis = semantic_result.get('modules_analysis', {})

        # 阶段1：产品功能域智能分组
        print("  → 阶段 1/3: 产品功能域分组...")
        product_grouping = await self._load_or_create_grouping(modules_analysis)

        if not product_grouping or not product_grouping.get('domains'):
            return {
                'success': False,
                'error': '无法生成产品功能域分组'
            }

        domains = product_grouping['domains']
        print(f"     识别到 {len(domains)} 个产品功能域\n")

        # 阶段2：按功能域生成 PRD
        print("  → 阶段 2/3: 生成 PRD 文档...")
        generated_count = 0
        skipped_count = 0
        failed_domains = []

        for idx, domain in enumerate(domains, 1):
            domain_name = domain['domain_name']
            print(f"     [{idx}/{len(domains)}] {domain_name}")

            try:
                result = await self._generate_domain_prd(
                    domain,
                    modules_analysis,
                    repo_path
                )

                if result['status'] == 'generated':
                    generated_count += 1
                elif result['status'] == 'skipped':
                    skipped_count += 1

            except Exception as e:
                print(f"       ❌ 失败: {str(e)}")
                failed_domains.append(domain_name)

        # 阶段3：生成导航索引
        print(f"\n  → 阶段 3/3: 生成导航索引...")
        await self._generate_index(product_grouping, repo_path)

        return {
            'success': True,
            'output_dir': self.prd_dir,
            'domains': domains,
            'generated_count': generated_count,
            'skipped_count': skipped_count,
            'failed_count': len(failed_domains)
        }

    async def _load_or_create_grouping(
        self,
        modules_analysis: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        加载或创建产品功能域分组

        Args:
            modules_analysis: 模块分析结果

        Returns:
            产品功能域分组结果
        """
        # 尝试加载缓存
        product_grouping = self.debug_helper.load_product_grouping()
        if product_grouping:
            return product_grouping

        # 执行智能分组
        product_grouping = await self._analyze_product_grouping(modules_analysis)

        # 保存分组结果
        if product_grouping:
            self.debug_helper.save_product_grouping(product_grouping)

        return product_grouping

    async def _analyze_product_grouping(
        self,
        modules_analysis: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        产品功能域智能分组

        Args:
            modules_analysis: 模块分析结果

        Returns:
            产品功能域分组结果
        """
        # 提取模块摘要信息（包括交互关系）
        modules_summary = []
        for module_name, module_data in modules_analysis.items():
            overview = module_data.get('overview', {})
            modules_summary.append({
                'module_name': module_name,
                'business_purpose': overview.get('business_purpose', ''),
                'core_features': overview.get('core_features', []),
                'external_interactions': overview.get('external_interactions', [])  # 包含交互关系
            })

        if not modules_summary:
            return None

        # 构建提示词
        prompt = PRDPromptBuilder.build_product_grouping_prompt(modules_summary)

        # 调用 Claude API
        response_text = None  # Initialize to avoid unbound variable
        try:
            # 使用独立的 session_id 避免上下文累积
            # 使用带重试的查询，验证返回的JSON包含product_domains字段且所有模块都被分配
            def validate_complete_grouping(r):
                if not r or not r.get('product_domains'):
                    return False
                # 检查是否所有模块都被分配
                product_domains = r.get('product_domains', [])
                assigned_modules = set()
                for domain in product_domains:
                    for module_name in domain.get('technical_modules', []):
                        assigned_modules.add(module_name)
                    # 也要检查子域中的模块
                    for sub_domain in domain.get('sub_domains', []):
                        for module_name in sub_domain.get('technical_modules', []):
                            assigned_modules.add(module_name)

                all_module_names = set(modules_analysis.keys())
                unassigned = all_module_names - assigned_modules

                if unassigned:
                    print(f"          ⚠️  有 {len(unassigned)} 个模块未被分配: {', '.join(list(unassigned)[:5])}{'...' if len(unassigned) > 5 else ''}")
                    return False
                return True

            response_text, grouping_data = await UnifiedQueryHelper.query_with_json_retry(
                client=self.client,
                prompt=prompt,
                session_id=self._get_session_id("doc_gen_grouping"),
                max_attempts=3,
                validator=validate_complete_grouping
            )

            product_domains = grouping_data.get('product_domains', [])

            # 构建映射关系
            module_to_domain_mapping = {}
            for domain in product_domains:
                domain_name = domain['domain_name']
                for module_name in domain['technical_modules']:
                    module_to_domain_mapping[module_name] = domain_name

            return {
                'domains': product_domains,
                'module_to_domain_mapping': module_to_domain_mapping
            }

        except json.JSONDecodeError as e:
            print(f"  ❌ JSON 解析失败: {str(e)}")
            if response_text:
                print(f"  响应内容: {response_text[:500]}...")
            else:
                print("  响应内容: 无法获取响应内容")
            return None
        except Exception as e:
            print(f"  ❌ 智能分组失败: {str(e)}")
            return None


    async def _generate_domain_prd(
        self,
        domain_info: Dict[str, Any],
        modules_analysis: Dict[str, Any],
        repo_path: str
    ) -> Dict[str, Any]:
        """
        生成单个产品功能域的PRD

        Args:
            domain_info: 功能域信息
            modules_analysis: 模块分析结果
            repo_path: 仓库路径

        Returns:
            生成结果
        """
        domain_name = domain_info['domain_name']
        technical_modules = domain_info.get('technical_modules', [])
        sub_domains = domain_info.get('sub_domains', [])

        # 检查缓存
        prd_file = self.debug_helper.check_prd_exists(Path(self.prd_dir), domain_name)
        if prd_file:
            return {'status': 'skipped', 'file': str(prd_file)}

        # 收集所有需要分析的技术模块（包括子域中的模块）
        all_modules_to_analyze = list(technical_modules)
        for sub_domain in sub_domains:
            all_modules_to_analyze.extend(sub_domain.get('technical_modules', []))

        # 聚合该功能域下所有技术模块的数据
        aggregated_modules_data = []
        for module_name in all_modules_to_analyze:
            if module_name in modules_analysis:
                module_data = modules_analysis[module_name]
                aggregated_modules_data.append({
                    'module_name': module_name,
                    'overview': module_data.get('overview', {}),
                    'detailed_analysis': module_data.get('detailed_analysis', {})
                })

        if not aggregated_modules_data:
            return {'status': 'failed', 'error': '没有有效模块数据'}

        # 估算token并决定是否需要分批
        estimated_tokens = self._estimate_modules_tokens(aggregated_modules_data)
        max_tokens_per_batch = 150000

        # 调用 Claude API
        try:
            if estimated_tokens <= max_tokens_per_batch:
                prd_content = await self._generate_prd_single_batch(
                    domain_info, aggregated_modules_data, repo_path
                )
            else:
                num_batches = (estimated_tokens // max_tokens_per_batch) + 1
                prd_content = await self._generate_prd_multi_batch(
                    domain_info, aggregated_modules_data, repo_path, num_batches
                )

            # 保存文档
            saved_file = self.debug_helper.save_prd_document(
                Path(self.prd_dir), domain_name, prd_content
            )

            if saved_file:
                return {'status': 'generated', 'file': str(saved_file)}
            else:
                return {'status': 'failed', 'error': '保存文档失败'}

        except Exception as e:
            print(f"  ❌ 生成失败: {str(e)}")
            return {'status': 'failed', 'error': str(e)}

    def _validate_prd_quality(self, doc_content: str) -> List[str]:
        """
        验证PRD质量

        Args:
            doc_content: 文档内容

        Returns:
            质量问题列表
        """
        issues = []

        # 检查禁止的技术术语
        forbidden_terms = [
            'function', 'method', 'class', 'object', 'API', 'endpoint',
            'parameter', 'argument', 'return', 'throw', 'catch',
            'interface', 'component', 'props', 'state'
        ]

        found_terms = []
        for term in forbidden_terms:
            # 使用单词边界匹配，避免误报
            pattern = r'\b' + term + r'\b'
            if re.search(pattern, doc_content, re.IGNORECASE):
                found_terms.append(term)

        if found_terms:
            issues.append(f"包含技术术语: {', '.join(found_terms[:5])}")

        # 检查必要章节
        required_sections = ['功能详细说明', '业务流程']
        missing_sections = []
        for section in required_sections:
            if section not in doc_content:
                missing_sections.append(section)

        if missing_sections:
            issues.append(f"缺少章节: {', '.join(missing_sections)}")

        # 检查文档长度（太短可能说明描述不够详细）
        if len(doc_content) < 500:
            issues.append("文档内容过短，可能描述不够详细")

        return issues

    async def _generate_index(
        self,
        product_grouping: Dict[str, Any],
        repo_path: str
    ) -> None:
        """
        生成导航索引

        Args:
            product_grouping: 产品功能域分组结果
            repo_path: 仓库路径
        """
        domains = product_grouping.get('domains', [])

        # 准备功能域信息
        all_domains_info = []
        for domain in domains:
            domain_name = domain['domain_name']
            safe_domain_name = re.sub(r'[^\w\-]', '_', domain_name)
            all_domains_info.append({
                'domain_name': domain_name,
                'domain_description': domain.get('domain_description', ''),
                'business_value': domain.get('business_value', ''),
                'prd_file': f"{safe_domain_name}.md"
            })

        # 构建提示词
        prompt = PRDPromptBuilder.build_index_prompt(
            all_domains_info,
            repo_path
        )

        # 调用 API
        try:
            # 使用独立的 session/thread 避免上下文累积
            index_content = await UnifiedQueryHelper.query_with_text(
                client=self.client,
                prompt=prompt,
                session_id=self._get_session_id("doc_gen_index")
            )

            # 保存 Index.md 到 prd 目录
            index_file = os.path.join(self.prd_dir, "Index.md")
            with open(index_file, 'w', encoding='utf-8') as f:
                f.write(index_content)

        except Exception as e:
            print(f"     ❌ 失败: {str(e)}")

    def _estimate_modules_tokens(self, modules_data: List[Dict]) -> int:
        """
        估算模块数据的token数量

        Args:
            modules_data: 模块数据列表

        Returns:
            估算的token数量

        估算规则：
        - 每个字符约 0.3-0.4 tokens（中英文混合）
        - JSON序列化后计算
        """
        json_str = json.dumps(modules_data, ensure_ascii=False)
        char_count = len(json_str)
        # 保守估计，使用 0.35 的转换比例
        estimated_tokens = int(char_count * 0.35)
        return estimated_tokens

    async def _generate_prd_single_batch(
        self,
        domain_info: Dict[str, Any],
        modules_data: List[Dict],
        repo_path: str
    ) -> str:
        """
        单批次生成PRD（原有逻辑）

        Args:
            domain_info: 功能域信息
            modules_data: 模块数据列表
            repo_path: 仓库路径

        Returns:
            生成的PRD内容
        """
        prompt = PRDPromptBuilder.build_domain_prd_prompt(
            domain_info, modules_data, repo_path
        )

        # 使用独立的 session/thread 避免上下文累积（每个domain使用独立线程）
        domain_name = domain_info.get('domain_name', 'unknown')
        session_key = f"doc_gen_prd_{domain_name}"

        prd_content = await UnifiedQueryHelper.query_with_text(
            client=self.client,
            prompt=prompt,
            session_id=self._get_session_id(session_key)
        )

        return prd_content

    async def _generate_prd_multi_batch(
        self,
        domain_info: Dict[str, Any],
        modules_data: List[Dict],
        repo_path: str,
        num_batches: int
    ) -> str:
        """
        多批次生成PRD并智能合并

        策略：
        1. 将模块均匀分配到各批次
        2. 第一批：生成完整框架 + 第一部分模块的详细内容
        3. 后续批次：只生成该批次模块的详细内容
        4. 最终合并：将所有批次的内容整合成完整PRD

        Args:
            domain_info: 功能域信息
            modules_data: 模块数据列表
            repo_path: 仓库路径
            num_batches: 批次数量

        Returns:
            合并后的完整PRD内容
        """
        domain_name = domain_info['domain_name']
        modules_per_batch = len(modules_data) // num_batches + 1

        batch_contents = []

        for batch_idx in range(num_batches):
            start_idx = batch_idx * modules_per_batch
            end_idx = min(start_idx + modules_per_batch, len(modules_data))
            batch_modules = modules_data[start_idx:end_idx]

            print(f"       批次 {batch_idx + 1}/{num_batches}: {len(batch_modules)} 个模块")

            try:
                if batch_idx == 0:
                    # 第一批：生成完整框架
                    prompt = PRDPromptBuilder.build_domain_prd_prompt_first_batch(
                        domain_info, batch_modules, len(modules_data), repo_path
                    )
                else:
                    # 后续批次：只生成该批次的详细内容
                    prompt = PRDPromptBuilder.build_domain_prd_prompt_continuation(
                        domain_info, batch_modules, batch_idx + 1, num_batches, repo_path
                    )

                # 同一domain的所有batch使用相同session/thread，保持上下文连续性
                # 这样后续batch可以参考第一批建立的框架和风格
                session_key = f"doc_gen_prd_{domain_name}"

                batch_content = await UnifiedQueryHelper.query_with_text(
                    client=self.client,
                    prompt=prompt,
                    session_id=self._get_session_id(session_key)
                )

                batch_contents.append(batch_content)

            except Exception as e:
                print(f"          ❌ 失败: {str(e)}")
                batch_contents.append(f"\n\n#### 批次 {batch_idx + 1} 生成失败\n原因: {str(e)}\n\n")

        # 智能合并所有批次
        merged_prd = self._merge_prd_batches(batch_contents)

        return merged_prd

    def _merge_prd_batches(
        self,
        batch_contents: List[str]
    ) -> str:
        """
        合并多个批次的PRD内容（改进版：更健壮、更准确）

        策略：
        - 第一批包含完整框架（第1章概述、第3-4章）
        - 后续批次包含第2章的部分内容
        - 合并时将后续批次的内容插入第2章和第3章之间

        改进点：
        1. 使用正则表达式精确匹配章节标题（行首）
        2. 清理后续批次的重复标题和元信息
        3. 标准化空行，保证格式一致
        4. 验证合并结果的完整性

        Args:
            batch_contents: 各批次的内容列表

        Returns:
            合并后的完整PRD
        """
        if len(batch_contents) == 1:
            return batch_contents[0]

        if not batch_contents:
            return ""

        first_batch = batch_contents[0]

        # 使用正则表达式精确匹配第3章标题（必须在行首）
        import re

        # 匹配各种可能的第3章标题格式
        chapter3_patterns = [
            r'^##\s*3[、:：.]?\s*跨功能交互',  # ## 3. 跨功能交互
            r'^##\s*第3章[、:：.]?\s*跨功能交互',  # ## 第3章：跨功能交互
            r'^##\s*3\s*$',  # ## 3
            r'^##\s*第3章\s*$',  # ## 第3章
            r'^###\s*3[、:：.]?\s*跨功能交互',  # ### 3. 跨功能交互
            r'^#\s*3[、:：.]?\s*跨功能交互',  # # 3. 跨功能交互
        ]

        chapter3_pos = -1
        for pattern in chapter3_patterns:
            match = re.search(pattern, first_batch, re.MULTILINE)
            if match:
                chapter3_pos = match.start()
                break

        if chapter3_pos <= 0:
            # 尝试更宽松的匹配
            fallback_match = re.search(r'^##\s*[第]?3', first_batch, re.MULTILINE)
            if fallback_match:
                chapter3_pos = fallback_match.start()

        if chapter3_pos > 0:
            # 找到了第3章，进行智能合并
            part1 = first_batch[:chapter3_pos]  # 第1-2章
            part2 = first_batch[chapter3_pos:]   # 第3-4章

            # 清理后续批次的内容
            cleaned_continuations = []
            for i, batch_content in enumerate(batch_contents[1:], 2):
                cleaned = self._clean_continuation_content(batch_content, i)
                if cleaned.strip():
                    cleaned_continuations.append(cleaned)
                else:
                    print(f"    ⚠️  批次 {i} 清理后内容为空，跳过")

            # 标准化第一部分的尾部空行
            part1 = part1.rstrip() + "\n\n"

            # 合并所有第2章的内容
            if cleaned_continuations:
                # 每个批次之间保持2个空行
                chapter2_continuation = "\n\n".join(cleaned_continuations)
                merged = part1 + chapter2_continuation + "\n\n" + part2
            else:
                # 没有后续内容，直接拼接
                merged = part1 + part2
        else:
            # 没找到章节标记，使用降级策略
            print("    ⚠️  未能识别章节结构，使用降级合并策略")

            # 清理后续批次
            all_parts = [first_batch.rstrip()]
            for i, batch_content in enumerate(batch_contents[1:], 2):
                cleaned = self._clean_continuation_content(batch_content, i)
                if cleaned.strip():
                    all_parts.append(cleaned.rstrip())

            # 使用明显的分隔符
            merged = "\n\n---\n\n".join(all_parts)

        # 标准化最终输出：去除多余空行（连续3个以上空行压缩为2个）
        merged = re.sub(r'\n{3,}', '\n\n', merged)

        return merged.strip() + "\n"

    def _clean_continuation_content(self, content: str, batch_num: int) -> str:
        """
        清理后续批次的内容，去除重复标题和元信息

        Args:
            content: 批次内容
            batch_num: 批次编号

        Returns:
            清理后的内容
        """
        import re

        # 去除前后空白
        cleaned = content.strip()

        # 去除可能的第2章重复标题（各种格式）
        chapter2_headers = [
            r'^##\s*第?2章[、:：.]?\s*功能详细说明\s*$',
            r'^##\s*2[、:：.]?\s*功能详细说明\s*$',
            r'^##\s*第?2章\s*$',
            r'^##\s*2\s*$',
            r'^###\s*第?2章',
            r'^#\s*第?2章',
        ]

        for pattern in chapter2_headers:
            # 只删除开头的章节标题
            cleaned = re.sub(pattern, '', cleaned, flags=re.MULTILINE, count=1)
            cleaned = cleaned.lstrip('\n')

        # 去除可能的元信息说明（如"继续第2章"、"本批次继续描述"等）
        meta_patterns = [
            r'^.*?继续.*?第[2二]章.*?$',
            r'^.*?本批次.*?$',
            r'^.*?接上.*?$',
        ]

        lines = cleaned.split('\n')
        filtered_lines = []
        for line in lines:
            is_meta = False
            for pattern in meta_patterns:
                if re.match(pattern, line.strip(), re.IGNORECASE):
                    is_meta = True
                    break
            if not is_meta:
                filtered_lines.append(line)

        cleaned = '\n'.join(filtered_lines).strip()

        return cleaned

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
# 独立测试入口
# ============================================================================

async def test_doc_generator():
    """测试文档生成功能"""
    import sys
    from pathlib import Path

    # 添加 src 到路径
    sys.path.insert(0, str(Path(__file__).parent.parent))

    from utils.debug_helper import DebugHelper

    print("\n" + "="*80)
    print("🧪 测试文档生成 Agent")
    print("="*80)

    # 初始化
    debug_helper = DebugHelper(enabled=True, verbose=True)
    generator = DocGeneratorAgent(debug_helper)

    # 加载语义分析结果
    print("\n📂 加载语义分析结果...")
    semantic_result = debug_helper.load_cached_data("02_semantic_analysis_final")

    if not semantic_result:
        print("❌ 未找到语义分析结果")
        print("   请先运行: python -m src.agents.semantic_analyzer_agent")
        return

    modules_count = len(semantic_result.get('modules_analysis', {}))
    print(f"✅ 已加载 {modules_count} 个模块的分析结果")

    # 获取仓库路径（从当前工作目录推断）
    repo_path = str(Path.cwd())
    print(f"📁 仓库路径: {repo_path}")

    # 生成 PRD 文档
    try:
        result = await generator.generate_prd_documents(
            semantic_result,
            repo_path
        )

        if result.get('success'):
            print("\n" + "="*80)
            print("✅ 测试完成！")
            print("="*80)
            print(f"📄 PRD 输出目录: {result['output_dir']}")
            print(f"🎯 产品功能域数量: {len(result['domains'])}")
            print(f"✍️  新生成文档: {result['generated_count']} 个")
            print(f"📦 跳过文档: {result['skipped_count']} 个")
            if result.get('failed_count', 0) > 0:
                print(f"❌ 失败文档: {result['failed_count']} 个")

            print("\n📋 生成的功能域:")
            for i, domain in enumerate(result['domains'], 1):
                print(f"  {i}. {domain['domain_name']}")
                print(f"     - {domain.get('domain_description', 'N/A')}")
        else:
            print(f"\n❌ 生成失败: {result.get('error')}")

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await generator.disconnect()


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_doc_generator())

