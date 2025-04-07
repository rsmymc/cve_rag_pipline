import numpy as np
from typing import List

class ChromaCompatibleEmbeddingFunction:
    def __init__(self, embedder):
        self.embedder = embedder

    def __call__(self, input: List[str]) -> List[np.ndarray]:
        vectors = self.embedder.embed_documents(input)
        return [np.array(v) for v in vectors]
