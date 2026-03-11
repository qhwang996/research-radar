# Implementation Guide

本文档为代码实现提供具体指导，包括接口定义、编码规范、测试要求等。

---

## 1. 核心原则

### 1.1 代码质量要求

- **简洁优先**：MVP阶段避免过度设计，保持代码简单直接
- **接口清晰**：每个模块有明确的输入输出
- **可测试性**：所有模块必须可单元测试
- **可观测性**：关键操作必须有日志
- **错误处理**：外部调用必须有异常处理

### 1.2 开发流程

1. 阅读接口定义
2. 编写单元测试（TDD）
3. 实现功能
4. 运行测试
5. 添加日志和文档
6. 代码格式化（black）

---

## 2. 接口定义

### 2.1 Crawler接口

所有爬虫必须继承 `BaseCrawler` 并实现以下方法：

```python
from abc import ABC, abstractmethod
from typing import List, Dict
from pathlib import Path

class BaseCrawler(ABC):
    """爬虫基类"""

    @abstractmethod
    def fetch_papers(self, years: List[int]) -> List[Dict]:
        """
        获取论文数据

        Args:
            years: 年份列表，如 [2024, 2025, 2026]

        Returns:
            论文字典列表，每个字典包含：
            - title: str (必需)
            - authors: List[str] (必需)
            - year: int (必需)
            - conference: str (必需)
            - source_url: str (必需)
            - paper_url: str (可选)
            - abstract: str (可选)
            - pdf_url: str (可选)

        Raises:
            CrawlerError: 爬取失败时抛出
        """
        pass

    @abstractmethod
    def save_raw(self, papers: List[Dict], output_dir: Path) -> Path:
        """
        保存原始数据到JSON文件

        Args:
            papers: 论文列表
            output_dir: 输出目录

        Returns:
            保存的文件路径
        """
        pass
```

**实现要求**：
- 必须有超时设置（建议10秒）
- 必须有重试机制（建议3次）
- 必须记录日志（开始、成功、失败）
- 保存的JSON必须包含元数据（source, fetched_at, total_papers）

---

### 2.2 Pipeline接口

所有数据处理管道必须继承 `BasePipeline`：

```python
from abc import ABC, abstractmethod
from typing import Any, List

class BasePipeline(ABC):
    """数据处理管道基类"""

    @abstractmethod
    def process(self, input_data: Any) -> Any:
        """
        处理数据

        Args:
            input_data: 输入数据

        Returns:
            处理后的数据

        Raises:
            PipelineError: 处理失败时抛出
        """
        pass

    def validate_input(self, data: Any) -> bool:
        """验证输入数据"""
        return True

    def validate_output(self, data: Any) -> bool:
        """验证输出数据"""
        return True
```

**实现要求**：
- 输入验证必须在处理前执行
- 输出验证必须在返回前执行
- 处理失败不应导致程序崩溃
- 必须记录处理统计（输入数量、输出数量、失败数量）

---

### 2.3 Scoring Strategy接口

所有评分策略必须继承 `BaseScoringStrategy`：

```python
from abc import ABC, abstractmethod
from src.models.artifact import Artifact
from src.models.profile import Profile

class BaseScoringStrategy(ABC):
    """评分策略基类"""

    @abstractmethod
    def calculate_score(self, artifact: Artifact, profile: Profile) -> float:
        """
        计算评分

        Args:
            artifact: 待评分的artifact
            profile: 用户profile

        Returns:
            评分，范围 0.0 - 1.0
        """
        pass

    @abstractmethod
    def get_strategy_name(self) -> str:
        """返回策略名称，用于标识和日志"""
        pass

    def get_weight(self) -> float:
        """返回策略权重，默认1.0"""
        return 1.0
```

**实现要求**：
- 评分必须在 0.0 - 1.0 范围内
- 策略名称必须唯一
- 必须可以独立测试（不依赖数据库）

---

## 3. 数据模型规范

### 3.1 基础模型要求

所有SQLAlchemy模型必须：

```python
from sqlalchemy import Column, Integer, DateTime, func
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class BaseModel:
    """所有模型的基类"""
    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
```

**要求**：
- 所有表必须有 id, created_at, updated_at
- 使用 UUID 作为 canonical_id（业务主键）
- 关键字段必须建索引
- 外键必须设置级联删除规则

### 3.2 Artifact模型示例

```python
from sqlalchemy import Column, String, Text, Float, JSON
from sqlalchemy.dialects.postgresql import UUID
import uuid

class Artifact(Base):
    __tablename__ = 'artifacts'

    id = Column(Integer, primary_key=True)
    canonical_id = Column(UUID(as_uuid=True), unique=True, default=uuid.uuid4, index=True)

    # 基础字段
    title = Column(String(500), nullable=False)
    authors = Column(JSON)  # List[str]
    year = Column(Integer, index=True)
    source_type = Column(String(50), index=True)  # papers/blogs/advisories
    source_url = Column(Text)

    # 内容字段
    abstract = Column(Text)
    summary_l1 = Column(Text)  # 一句话摘要
    summary_l2 = Column(Text)  # 三段式摘要
    summary_l3 = Column(Text)  # 详细分析

    # 评分字段
    recency_score = Column(Float)
    authority_score = Column(Float)
    relevance_score = Column(Float)
    final_score = Column(Float, index=True)

    # 元数据
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
```

---

## 4. LLM调用规范

### 4.1 LLM Client接口

```python
from typing import Optional, Dict, Any
from enum import Enum

class ModelTier(Enum):
    FAST = "fast"      # GPT-4o-mini
    STANDARD = "standard"  # GPT-4o / Claude 3.5 Sonnet
    PREMIUM = "premium"    # Claude Opus

class LLMClient:
    """LLM客户端封装"""

    def generate(
        self,
        prompt: str,
        model_tier: ModelTier = ModelTier.STANDARD,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        cache_key: Optional[str] = None
    ) -> str:
        """
        生成文本

        Args:
            prompt: 提示词
            model_tier: 模型等级
            max_tokens: 最大token数
            temperature: 温度参数
            cache_key: 缓存键，如果提供则启用缓存

        Returns:
            生成的文本

        Raises:
            LLMError: 调用失败时抛出
        """
        pass
```

**实现要求**：
- 必须支持缓存（相同cache_key返回缓存结果）
- 必须有重试机制（失败重试3次，指数退避）
- 必须有超时设置（60秒）
- 必须记录token消耗
- 必须处理rate limit错误

### 4.2 成本控制策略

```python
# 快速筛选：使用FAST模型
summary_l1 = llm_client.generate(
    prompt=f"用一句话总结：{title}",
    model_tier=ModelTier.FAST,
    cache_key=f"summary_l1_{artifact_id}"
)

# 日常分析：使用STANDARD模型
summary_l2 = llm_client.generate(
    prompt=summarize_prompt,
    model_tier=ModelTier.STANDARD,
    cache_key=f"summary_l2_{artifact_id}"
)

# 深度分析：使用PREMIUM模型（仅周度）
candidate_directions = llm_client.generate(
    prompt=direction_prompt,
    model_tier=ModelTier.PREMIUM
)
```

---

## 5. 错误处理规范

### 5.1 自定义异常

```python
class ResearchRadarError(Exception):
    """基础异常类"""
    pass

class CrawlerError(ResearchRadarError):
    """爬虫错误"""
    pass

class PipelineError(ResearchRadarError):
    """管道处理错误"""
    pass

class LLMError(ResearchRadarError):
    """LLM调用错误"""
    pass

class DatabaseError(ResearchRadarError):
    """数据库错误"""
    pass
```

### 5.2 错误处理模式

```python
import logging
from typing import Optional

logger = logging.getLogger(__name__)

def safe_crawl(crawler, years):
    """安全的爬虫调用"""
    try:
        papers = crawler.fetch_papers(years)
        logger.info(f"Successfully fetched {len(papers)} papers")
        return papers
    except CrawlerError as e:
        logger.error(f"Crawler failed: {e}")
        return []
    except Exception as e:
        logger.critical(f"Unexpected error: {e}")
        raise
```

**要求**：
- 预期的错误使用自定义异常
- 记录详细的错误日志
- 关键操作失败不应导致整个流程崩溃
- 使用合适的日志级别

---

## 6. 日志规范

### 6.1 日志配置

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/research_radar.log'),
        logging.StreamHandler()
    ]
)
```

### 6.2 日志级别使用

- **DEBUG**: 详细的调试信息（变量值、中间结果）
- **INFO**: 关键操作（开始处理、完成处理、统计信息）
- **WARNING**: 警告信息（数据不完整、API限流、降级处理）
- **ERROR**: 错误信息（处理失败、API错误、数据验证失败）
- **CRITICAL**: 严重错误（数据库连接失败、配置错误）

### 6.3 日志示例

```python
logger.info(f"Starting normalization pipeline for {len(raw_data)} items")
logger.debug(f"Processing item: {item_id}")
logger.warning(f"Missing abstract for paper: {paper_title}")
logger.error(f"Failed to generate summary: {error}")
logger.info(f"Normalization complete: {success_count} success, {fail_count} failed")
```

---

## 7. 测试规范

### 7.1 单元测试

```python
import pytest
from src.scoring.recency_strategy import RecencyStrategy
from src.models.artifact import Artifact
from datetime import datetime, timedelta

def test_recency_strategy_recent_paper():
    """测试最近论文的评分"""
    strategy = RecencyStrategy()

    # 创建测试数据
    artifact = Artifact(
        title="Test Paper",
        year=datetime.now().year,
        created_at=datetime.now()
    )

    # 执行测试
    score = strategy.calculate_score(artifact, None)

    # 验证结果
    assert 0.8 <= score <= 1.0, "Recent paper should have high score"

def test_recency_strategy_old_paper():
    """测试旧论文的评分"""
    strategy = RecencyStrategy()

    artifact = Artifact(
        title="Old Paper",
        year=datetime.now().year - 5,
        created_at=datetime.now() - timedelta(days=365*5)
    )

    score = strategy.calculate_score(artifact, None)

    assert 0.0 <= score <= 0.5, "Old paper should have low score"
```

**要求**：
- 每个公共方法必须有测试
- 测试必须独立（不依赖其他测试）
- 使用Mock隔离外部依赖
- 测试名称清晰描述测试内容

### 7.2 集成测试

```python
def test_full_pipeline():
    """测试完整数据流"""
    # 1. 爬取数据
    crawler = NDSSCrawler()
    papers = crawler.fetch_papers([2025])

    # 2. 归一化
    pipeline = NormalizationPipeline()
    artifacts = pipeline.process(papers)

    # 3. 评分
    scorer = CompositeScorer()
    scored_artifacts = scorer.score_all(artifacts)

    # 4. 验证
    assert len(scored_artifacts) > 0
    assert all(a.final_score is not None for a in scored_artifacts)
```

---

## 8. 配置管理

### 8.1 环境变量

```bash
# .env
DATABASE_URL=sqlite:///data/research_radar.db
OPENAI_API_KEY=sk-xxx
ANTHROPIC_API_KEY=sk-ant-xxx
LOG_LEVEL=INFO
CACHE_DIR=data/cache
```

### 8.2 配置类

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    openai_api_key: str
    anthropic_api_key: str
    log_level: str = "INFO"
    cache_dir: str = "data/cache"

    class Config:
        env_file = ".env"

settings = Settings()
```

---

## 9. 代码风格

### 9.1 格式化

使用 black 格式化代码：

```bash
black src/ tests/
```

### 9.2 Linting

使用 ruff 检查代码：

```bash
ruff check src/ tests/
```

### 9.3 类型注解

```python
from typing import List, Dict, Optional

def process_papers(
    papers: List[Dict[str, Any]],
    profile: Optional[Profile] = None
) -> List[Artifact]:
    """处理论文数据"""
    pass
```

---

## 10. 文档字符串

使用Google风格的docstring：

```python
def calculate_score(artifact: Artifact, profile: Profile) -> float:
    """
    计算artifact的评分

    Args:
        artifact: 待评分的artifact对象
        profile: 用户profile对象

    Returns:
        评分，范围0.0-1.0

    Raises:
        ValueError: 如果artifact或profile为None

    Example:
        >>> artifact = Artifact(title="Test")
        >>> profile = Profile(interests=["security"])
        >>> score = calculate_score(artifact, profile)
        >>> assert 0.0 <= score <= 1.0
    """
    pass
```

---

## 11. Review Checklist

代码提交前检查：

- [ ] 是否符合接口定义
- [ ] 是否有单元测试且通过
- [ ] 是否有适当的日志
- [ ] 是否有异常处理
- [ ] 是否有文档字符串
- [ ] 是否通过black格式化
- [ ] 是否通过ruff检查
- [ ] 是否有类型注解
- [ ] 是否避免了不必要的复杂度
- [ ] 是否有安全问题（API key泄露、SQL注入等）

---

## 12. 常见模式

### 12.1 Repository模式

**实际实现参考** (src/repositories/base.py):

```python
from typing import Generic, TypeVar
from sqlalchemy.orm import Session

ModelType = TypeVar("ModelType", bound=Base)

class BaseRepository(Generic[ModelType]):
    """泛型Repository基类"""

    def __init__(self, session: Session, model_type: type[ModelType]):
        self.session = session
        self.model_type = model_type

    def get_by_id(self, record_id: int) -> ModelType | None:
        return self.session.get(self.model_type, record_id)

    def save(self, instance: ModelType) -> ModelType:
        try:
            self.session.add(instance)
            self.session.commit()
            self.session.refresh(instance)
            return instance
        except SQLAlchemyError as exc:
            self.session.rollback()
            raise DatabaseError(f"Failed to save") from exc
```

**具体Repository示例** (src/repositories/artifact_repository.py):

```python
class ArtifactRepository(BaseRepository[Artifact]):
    def __init__(self, session: Session):
        super().__init__(session, Artifact)

    def get_by_canonical_id(self, canonical_id: str) -> Artifact | None:
        stmt = select(Artifact).where(Artifact.canonical_id == canonical_id)
        return self.session.scalar(stmt)
```

### 12.2 Factory模式

```python
class CrawlerFactory:
    """爬虫工厂"""

    @staticmethod
    def create(source: str) -> BaseCrawler:
        crawlers = {
            'ndss': NDSSCrawler,
            'sp': SPCrawler,
            'ccs': CCSCrawler,
        }

        crawler_class = crawlers.get(source.lower())
        if not crawler_class:
            raise ValueError(f"Unknown source: {source}")

        return crawler_class()
```

---

下一部分将在单独的文件中继续...
