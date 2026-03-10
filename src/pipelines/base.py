"""Shared pipeline primitives."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BasePipeline(ABC):
    """Base class for data processing pipelines."""

    @abstractmethod
    def process(self, input_data: Any) -> Any:
        """
        Process input data into a normalized output.

        Args:
            input_data: Source data consumed by the pipeline.

        Returns:
            Pipeline output.
        """

    def validate_input(self, data: Any) -> bool:
        """Return whether the input data is valid for processing."""

        return True

    def validate_output(self, data: Any) -> bool:
        """Return whether the pipeline output satisfies basic invariants."""

        return True
