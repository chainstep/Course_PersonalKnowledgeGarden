from __future__ import annotations

import hashlib
import math
import re
from abc import ABC, abstractmethod


class EmbeddingBackend(ABC):
    model_name: str
    dimension: int

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class FakeEmbeddingBackend(EmbeddingBackend):
    def __init__(self, dimension: int = 32, model_name: str = "fake-v1") -> None:
        self.dimension = dimension
        self.model_name = model_name

    def embed(self, texts: list[str]) -> list[list[float]]:
        output: list[list[float]] = []
        for text in texts:
            vector = [0.0] * self.dimension
            for token in re.findall(r"\w+", text.lower()):
                digest = hashlib.sha256(token.encode()).digest()
                index = int.from_bytes(digest[:4], "big") % self.dimension
                vector[index] += 1.0 if digest[4] % 2 else -1.0
            norm = math.sqrt(sum(x * x for x in vector)) or 1.0
            output.append([x / norm for x in vector])
        return output
