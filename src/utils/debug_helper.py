"""
Debug 辅助工具

用于保存分析过程中的中间结果，方便调试和问题排查
"""

import json
import datetime
from pathlib import Path
from typing import Any, Optional

import config


class DebugHelper:
    """Debug 辅助类"""

    def __init__(self, enabled: bool = False, verbose: bool = False):
        """
        初始化 Debug Helper

        Args:
            enabled: 是否启用 debug 模式
            verbose: 是否输出详细日志
        """
        self.enabled = enabled
        self.verbose = verbose
        self._debug_dir_ensured = False

    @property
    def debug_dir(self):
        """动态获取 debug 目录"""
        if self.enabled and not self._debug_dir_ensured:
            config.ensure_debug_dir()
            self._log(f"🐛 调试模式已启用，中间结果将保存到: {config.DEBUG_DIR}")
            self._debug_dir_ensured = True
        return config.DEBUG_DIR

    def save_stage_data(self, stage: str, raw_response: str, extracted_data: Any):
        """
        保存分析阶段的数据

        Args:
            stage: 阶段名称（如 "01_overview", "02_module_01"）
            raw_response: 原始响应文本
            extracted_data: 提取的结构化数据
        """
        if not self.enabled:
            return

        # 清理 stage 名称，替换不安全的文件名字符
        import re
        safe_stage = re.sub(r'[^\w\-]', '_', stage)

        timestamp = self._get_timestamp()

        # 保存原始响应
        raw_file = self.debug_dir / f"{timestamp}_{safe_stage}_raw.txt"
        with open(raw_file, 'w', encoding='utf-8') as f:
            f.write(raw_response)

        # 保存提取的数据
        extracted_file = self.debug_dir / f"{timestamp}_{safe_stage}_extracted.json"
        with open(extracted_file, 'w', encoding='utf-8') as f:
            json.dump(extracted_data, f, ensure_ascii=False, indent=2)

        self._log(f"  🐛 调试数据已保存: {safe_stage}")
        self._log(f"     - 原始响应: {raw_file.name}")
        self._log(f"     - 提取结果: {extracted_file.name}")

    def save_document(self, stage: str, document: str):
        """
        保存文档阶段的数据

        Args:
            stage: 阶段名称（如 "04_document"）
            document: 生成的文档内容
        """
        if not self.enabled:
            return

        # 清理 stage 名称，替换不安全的文件名字符
        import re
        safe_stage = re.sub(r'[^\w\-]', '_', stage)

        timestamp = self._get_timestamp()
        doc_file = self.debug_dir / f"{timestamp}_{safe_stage}.md"

        with open(doc_file, 'w', encoding='utf-8') as f:
            f.write(document)

        self._log(f"  🐛 调试数据已保存: {safe_stage}")
        self._log(f"     - 生成文档: {doc_file.name}")

    def save_error(self, stage: str, error: Exception, context: Optional[dict] = None):
        """
        保存错误信息

        Args:
            stage: 发生错误的阶段
            error: 异常对象
            context: 上下文信息（可选）
        """
        if not self.enabled:
            return

        # 清理 stage 名称，替换不安全的文件名字符
        import re
        safe_stage = re.sub(r'[^\w\-]', '_', stage)

        timestamp = self._get_timestamp()
        error_file = self.debug_dir / f"{timestamp}_{safe_stage}_error.json"

        error_data = {
            "stage": stage,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "timestamp": timestamp,
            "context": context or {}
        }

        with open(error_file, 'w', encoding='utf-8') as f:
            json.dump(error_data, f, ensure_ascii=False, indent=2)

        self._log(f"  🐛 错误信息已保存: {error_file.name}")

    @staticmethod
    def _get_timestamp() -> str:
        """获取当前时间戳"""
        return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    def _log(self, message: str):
        """输出日志"""
        if self.verbose:
            print(message)

    def load_cached_document(self, stage: str) -> Optional[str]:
        """
        加载缓存的文档（Markdown 格式）

        Args:
            stage: 阶段名称（如 "04_document"）

        Returns:
            缓存的文档内容，如果不存在或读取失败则返回 None
        """
        if not self.enabled or self.debug_dir is None or not self.debug_dir.exists():
            return None

        # 清理 stage 名称，替换不安全的文件名字符
        import re
        safe_stage = re.sub(r'[^\w\-]', '_', stage)

        # 查找最新的该阶段的 .md 文件
        pattern = f"*_{safe_stage}.md"
        files = sorted(self.debug_dir.glob(pattern), reverse=True)

        if not files:
            return None

        latest_file = files[0]

        try:
            with open(latest_file, 'r', encoding='utf-8') as f:
                content = f.read()

            self._log(f"  📦 使用缓存文档: {latest_file.name}")
            return content
        except Exception as e:
            self._log(f"  ⚠️  缓存读取失败: {e}")
            return None

    def load_cached_data(self, stage: str) -> Optional[dict]:
        """
        加载缓存的分析数据（如果存在）

        Args:
            stage: 阶段名称（如 "01_overview", "02_module_01"）

        Returns:
            缓存的数据，如果不存在或读取失败则返回 None
        """
        if not self.enabled or self.debug_dir is None or not self.debug_dir.exists():
            return None

        # 清理 stage 名称，替换不安全的文件名字符
        import re
        safe_stage = re.sub(r'[^\w\-]', '_', stage)

        # 查找最新的该阶段的 extracted.json 文件
        pattern = f"*_{safe_stage}_extracted.json"
        files = sorted(self.debug_dir.glob(pattern), reverse=True)

        if not files:
            return None

        latest_file = files[0]

        try:
            with open(latest_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self._log(f"  📦 使用缓存数据: {latest_file.name}")
            return data
        except Exception as e:
            self._log(f"  ⚠️  缓存读取失败: {e}")
            return None

    def get_debug_summary(self) -> dict:
        """
        获取 debug 文件摘要

        Returns:
            包含 debug 文件统计信息的字典
        """
        if not self.enabled or self.debug_dir is None or not self.debug_dir.exists():
            return {"enabled": False}

        files = list(self.debug_dir.glob("*"))

        # 按类型统计
        stats = {
            "enabled": True,
            "debug_dir": str(self.debug_dir),
            "total_files": len(files),
            "by_type": {
                "raw": len([f for f in files if f.name.endswith("_raw.txt")]),
                "extracted": len([f for f in files if f.name.endswith("_extracted.json")]),
                "documents": len([f for f in files if f.suffix == ".md"]),
                "errors": len([f for f in files if f.name.endswith("_error.json")]),
            }
        }

        return stats

    # ========================================================================
    # PRD文档生成缓存相关方法
    # ========================================================================

    def load_product_grouping(self) -> Optional[dict]:
        """
        加载产品功能域分组缓存

        Returns:
            产品功能域分组结果，如果不存在或加载失败则返回 None
        """
        grouping_file = self.debug_dir / "product_grouping.json"

        if not grouping_file.exists():
            return None

        try:
            with open(grouping_file, 'r', encoding='utf-8') as f:
                product_grouping = json.load(f)

            self._log(f"  📦 使用缓存的产品功能域分组")
            return product_grouping
        except Exception as e:
            self._log(f"  ⚠️  加载产品功能域分组失败: {str(e)}")
            return None

    def save_product_grouping(self, product_grouping: dict) -> bool:
        """
        保存产品功能域分组结果

        Args:
            product_grouping: 产品功能域分组结果

        Returns:
            是否保存成功
        """
        grouping_file = self.debug_dir / "product_grouping.json"

        try:
            with open(grouping_file, 'w', encoding='utf-8') as f:
                json.dump(product_grouping, f, ensure_ascii=False, indent=2)

            self._log(f"  💾 产品功能域分组已保存: {grouping_file.name}")
            return True
        except Exception as e:
            self._log(f"  ⚠️  保存产品功能域分组失败: {str(e)}")
            return False

    def check_prd_exists(self, prd_dir: Path, domain_name: str) -> Optional[Path]:
        """
        检查PRD文档是否已存在

        Args:
            prd_dir: PRD输出目录
            domain_name: 功能域名称

        Returns:
            PRD文件路径（如果存在），否则返回 None
        """
        import re

        # 安全化文件名
        safe_domain_name = re.sub(r'[^\w\-]', '_', domain_name)
        prd_file = prd_dir / f"{safe_domain_name}.md"

        if prd_file.exists():
            self._log(f"  📦 使用已有PRD文档: {safe_domain_name}.md")
            return prd_file

        return None

    def save_prd_document(self, prd_dir: Path, domain_name: str, content: str) -> Optional[Path]:
        """
        保存PRD文档

        Args:
            prd_dir: PRD输出目录
            domain_name: 功能域名称
            content: 文档内容

        Returns:
            保存的文件路径，失败返回 None
        """
        import re

        # 安全化文件名
        safe_domain_name = re.sub(r'[^\w\-]', '_', domain_name)
        prd_file = prd_dir / f"{safe_domain_name}.md"

        try:
            with open(prd_file, 'w', encoding='utf-8') as f:
                f.write(content)

            self._log(f"  💾 PRD文档已保存: {safe_domain_name}.md")
            return prd_file
        except Exception as e:
            self._log(f"  ⚠️  保存PRD文档失败: {str(e)}")
            return None

    # ========================================================================
    # 批次分析相关方法
    # ========================================================================

    def find_latest_batch_directory(self, module_name: str) -> Optional[Path]:
        """
        查找最新的批次目录

        Args:
            module_name: 模块名称

        Returns:
            最新的批次目录路径，如果不存在则返回 None
        """
        import re

        if not self.enabled or self.debug_dir is None or not self.debug_dir.exists():
            return None

        # 清理模块名（移除特殊字符）
        safe_module_name = re.sub(r'[^\w\-]', '_', module_name)

        # 查找匹配的批次目录
        pattern = f"*_{safe_module_name}_batches"
        batch_dirs = sorted(self.debug_dir.glob(pattern), reverse=True)

        if batch_dirs:
            latest_dir = batch_dirs[0]
            self._log(f"  📦 找到批次目录: {latest_dir.name}")
            return latest_dir

        return None

    def create_batch_directory(self, module_name: str) -> Path:
        """
        创建批次专用目录（如果已存在则复用）

        Args:
            module_name: 模块名称

        Returns:
            批次目录路径
        """
        import re

        if not self.enabled:
            # 即使不启用debug，也返回一个临时目录
            return self.debug_dir / "temp_batches"

        # 先尝试查找已有的批次目录
        existing_dir = self.find_latest_batch_directory(module_name)
        if existing_dir:
            self._log(f"  🔄 复用批次目录: {existing_dir.name}")
            return existing_dir

        # 创建时间戳
        timestamp = self._get_timestamp()

        # 清理模块名（移除特殊字符）
        safe_module_name = re.sub(r'[^\w\-]', '_', module_name)

        # 创建批次目录
        batch_dir = self.debug_dir / f"{timestamp}_{safe_module_name}_batches"
        batch_dir.mkdir(parents=True, exist_ok=True)

        self._log(f"  📁 创建批次目录: {batch_dir.name}")

        return batch_dir

    def load_batches_info(self, batch_dir: Path, module_name: str) -> Optional[list]:
        """
        加载已保存的批次信息

        Args:
            batch_dir: 批次目录
            module_name: 模块名称

        Returns:
            批次列表，如果不存在或加载失败则返回 None
        """
        if not self.enabled or batch_dir is None or not batch_dir.exists():
            return None

        # 清理模块名
        import re
        safe_module_name = re.sub(r'[^\w\-]', '_', module_name)

        summary_file = batch_dir / f"{safe_module_name}_batches_summary.json"

        if not summary_file.exists():
            return None

        try:
            # 加载批次统计信息
            with open(summary_file, 'r', encoding='utf-8') as f:
                summary = json.load(f)

            total_batches = summary.get('total_batches', 0)

            if total_batches == 0:
                return None

            # 加载每个批次的详细信息
            batches = []
            for idx in range(1, total_batches + 1):
                batch_detail_file = batch_dir / f"{safe_module_name}_batch_{idx:02d}_info.json"

                if not batch_detail_file.exists():
                    self._log(f"  ⚠️  批次{idx}详情文件不存在")
                    return None

                with open(batch_detail_file, 'r', encoding='utf-8') as f:
                    batch_info = json.load(f)
                    batches.append(batch_info)

            self._log(f"  📦 加载批次信息: {len(batches)} 个批次")
            return batches

        except Exception as e:
            self._log(f"  ⚠️  批次信息加载失败: {e}")
            return None

    def save_batches_info(
        self, batch_dir: Path, module_name: str, batches: list, all_files: list
    ):
        """
        保存批次详情信息

        Args:
            batch_dir: 批次目录
            module_name: 模块名称
            batches: 批次列表
            all_files: 所有文件信息
        """
        if not self.enabled:
            return

        # 清理模块名
        import re
        safe_module_name = re.sub(r'[^\w\-]', '_', module_name)

        # 准备批次统计信息
        batches_summary = {
            "total_batches": len(batches),
            "total_files": len(all_files),
            "batches": []
        }

        for idx, batch in enumerate(batches, 1):
            batch_info = {
                "batch_id": idx,
                "file_count": len(batch['files']),
                "estimated_tokens": batch['estimated_tokens'],
                "cohesion": batch['cohesion'],
                "description": batch['description'],
                "file_paths": [f['path'] for f in batch['files']]
            }
            batches_summary["batches"].append(batch_info)

            # 保存每个批次的详细信息（文件名包含模块名）
            batch_detail_file = batch_dir / f"{safe_module_name}_batch_{idx:02d}_info.json"
            with open(batch_detail_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "batch_id": idx,
                    "files": batch['files'],
                    "estimated_tokens": batch['estimated_tokens'],
                    "cohesion": batch['cohesion'],
                    "description": batch['description']
                }, f, ensure_ascii=False, indent=2)

        # 保存批次统计（文件名包含模块名）
        summary_file = batch_dir / f"{safe_module_name}_batches_summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(batches_summary, f, ensure_ascii=False, indent=2)

        self._log(f"  📊 批次信息已保存: {len(batches)} 个批次")

    def save_batch_result(
        self,
        batch_dir: Path,
        module_name: str,
        batch_idx: int,
        response_text: str,
        batch_result: dict,
        batch_info: dict
    ):
        """
        保存单个批次的分析结果

        Args:
            batch_dir: 批次目录
            module_name: 模块名称
            batch_idx: 批次索引
            response_text: AI原始响应
            batch_result: 提取的JSON结果
            batch_info: 批次信息
        """
        if not self.enabled:
            return

        # 清理模块名
        import re
        safe_module_name = re.sub(r'[^\w\-]', '_', module_name)

        # 确保目录存在
        batch_dir.mkdir(parents=True, exist_ok=True)

        # 保存原始响应（文件名包含模块名）
        raw_file = batch_dir / f"{safe_module_name}_batch_{batch_idx:02d}_raw.txt"
        try:
            with open(raw_file, 'w', encoding='utf-8') as f:
                f.write(response_text)
        except Exception as e:
            self._log(f"  ⚠️  批次{batch_idx} 原始响应保存失败: {e}")

        # 保存提取的结果（文件名包含模块名）
        result_file = batch_dir / f"{safe_module_name}_batch_{batch_idx:02d}_result.json"
        try:
            # 先序列化为字符串，确认数据可序列化
            json_str = json.dumps(batch_result, ensure_ascii=False, indent=2)
            # 再写入文件
            with open(result_file, 'w', encoding='utf-8') as f:
                f.write(json_str)
        except (TypeError, ValueError, IOError, OSError) as e:
            # 如果序列化或写入失败，打印精简日志
            files_count = len(batch_result.get('files_analysis', [])) if isinstance(batch_result, dict) else 'N/A'
            print(f"  ⚠️  批次{batch_idx} JSON保存失败: {type(e).__name__}: {e} (files: {files_count})")

        self._log(f"  💾 批次{batch_idx}结果已保存")

    def load_batch_result(self, batch_dir: Path, module_name: str, batch_idx: int) -> Optional[dict]:
        """
        加载已保存的批次结果

        Args:
            batch_dir: 批次目录
            module_name: 模块名称
            batch_idx: 批次索引

        Returns:
            批次结果字典，如果不存在或加载失败则返回 None
        """
        if not self.enabled:
            return None

        # 清理模块名
        import re
        safe_module_name = re.sub(r'[^\w\-]', '_', module_name)

        result_file = batch_dir / f"{safe_module_name}_batch_{batch_idx:02d}_result.json"

        if not result_file.exists():
            return None

        try:
            with open(result_file, 'r', encoding='utf-8') as f:
                batch_result = json.load(f)

            self._log(f"  📦 加载批次{batch_idx}缓存")
            return batch_result
        except Exception as e:
            self._log(f"  ⚠️  批次{batch_idx}缓存加载失败: {e}")
            return None

