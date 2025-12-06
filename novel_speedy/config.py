# novel_speedy/config.py
"""
统一配置管理

所有可配置项集中在此，避免硬编码分散在各模块中。
配置优先级：环境变量 > .env 文件 > 默认值
"""

import os
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

from dotenv import load_dotenv

_project_root = Path(__file__).parent.parent
_env_file = _project_root / ".env"
load_dotenv(_env_file)


def _get_env(key: str, default: str="") -> str:
    """获取环境变量，如果不存在则返回默认值"""
    return os.getenv(key, default)


def _get_env_int(key: str, default: int) -> int:
    """获取整数类型的环境变量"""
    value = os.getenv(key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _get_env_float(key: str, default: float) -> float:
    """获取浮点数类型的环境变量"""
    value = os.getenv(key)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _get_env_bool(key: str, default: bool) -> bool:
    """获取布尔类型的环境变量"""
    value = os.getenv(key)
    if value is None:
        return default
    return value.lower() in ("true", "1", "yes", "on")


@dataclass
class LLMConfig:
    """LLM API 配置"""
    api_url: str = field(
        default_factory=lambda: _get_env("LLM_API_URL")
    )
    model: str = field(
        default_factory=lambda: _get_env("LLM_MODEL")
    )
    max_retries: int = field(
        default_factory=lambda: _get_env_int("LLM_MAX_RETRIES", 2)
    )
    retry_delay: float = field(
        default_factory=lambda: _get_env_float("LLM_RETRY_DELAY", 1.0)
    )
    timeout: int = field(
        default_factory=lambda: _get_env_int("LLM_TIMEOUT", 120)
    )
    default_temperature: float = field(
        default_factory=lambda: _get_env_float("LLM_DEFAULT_TEMPERATURE", 0.2)
    )
    default_max_tokens: int = field(
        default_factory=lambda: _get_env_int("LLM_DEFAULT_MAX_TOKENS", 1024)
    )


@dataclass
class PathConfig:
    """路径配置"""
    base_dir: str = field(
        default_factory=lambda: _get_env(
            "PROJECT_BASE_DIR",
            str(Path(__file__).parent.parent)
        )
    )
    
    @property
    def data_dir(self) -> str:
        """数据根目录"""
        return os.path.join(self.base_dir, "data")
    
    @property
    def input_dir(self) -> str:
        """输入文件目录"""
        return os.path.join(self.data_dir, "input")
    
    @property
    def output_dir(self) -> str:
        """输出文件目录"""
        return os.path.join(self.data_dir, "output")
    
    def ensure_dirs(self) -> None:
        """确保所有目录存在"""
        os.makedirs(self.input_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)


@dataclass
class ConcurrencyConfig:
    """并发控制配置"""
    enabled: bool = field(
        default_factory=lambda: _get_env_bool("ENABLE_CONCURRENT", False)
    )
    max_workers: int = field(
        default_factory=lambda: _get_env_int("MAX_WORKERS", 4)
    )
    

@dataclass 
class Config:
    """全局配置"""
    llm: LLMConfig = field(default_factory=LLMConfig)
    paths: PathConfig = field(default_factory=PathConfig)
    concurrency: ConcurrencyConfig = field(default_factory=ConcurrencyConfig)
    
    def __post_init__(self):
        """初始化后确保目录存在"""
        self.paths.ensure_dirs()
    
    def print_config(self) -> None:
        """打印当前配置（用于调试）"""
        print("=" * 50)
        print("当前配置:")
        print("=" * 50)
        print(f"[LLM]")
        print(f"  API URL: {self.llm.api_url}")
        print(f"  Model: {self.llm.model}")
        print(f"  Max Retries: {self.llm.max_retries}")
        print(f"  Timeout: {self.llm.timeout}s")
        print(f"  Temperature: {self.llm.default_temperature}")
        print(f"  Max Tokens: {self.llm.default_max_tokens}")
        print(f"[Paths]")
        print(f"  Base: {self.paths.base_dir}")
        print(f"  Input: {self.paths.input_dir}")
        print(f"  Output: {self.paths.output_dir}")
        print(f"[Concurrency]")
        print(f"  Enabled: {self.concurrency.enabled}")
        print(f"  Max Workers: {self.concurrency.max_workers}")
        print("=" * 50)


# 全局配置实例（单例）
config = Config()


def get_config() -> Config:
    """获取全局配置实例"""
    return config


def reload_config() -> Config:
    """重新加载配置（重新读取环境变量）"""
    global config
    load_dotenv(_env_file, override=True)
    config = Config()
    return config


def update_llm_config(
    api_url: Optional[str] = None,
    model: Optional[str] = None,
    max_retries: Optional[int] = None,
    timeout: Optional[int] = None
) -> None:
    """
    运行时更新 LLM 配置
    
    Args:
        api_url: API 地址
        model: 模型名称
        max_retries: 最大重试次数
        timeout: 超时时间（秒）
    """
    if api_url is not None:
        config.llm.api_url = api_url
    if model is not None:
        config.llm.model = model
    if max_retries is not None:
        config.llm.max_retries = max_retries
    if timeout is not None:
        config.llm.timeout = timeout
