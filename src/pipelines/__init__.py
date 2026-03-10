"""Data processing pipelines."""

from src.pipelines.base import BasePipeline
from src.pipelines.normalization import NormalizationPipeline

__all__ = ["BasePipeline", "NormalizationPipeline"]
