import json 
import math
from pathlib import Path

def cosine(a: list[float], b: list[float])->float:
    """Compute the cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0

class VectorStore:
    """A simple vector store that stores vectors and their associated metadata."""

    def __init__(self, path:Path)->None:
        self.path = Path(path)
        self.records: list[dict] = []
    def load(self)->None:
        if self.path.exists():
            self.records = json.loads(self.path.read_text())
    def save(self)->None:
        self.path.parent.mkdir(parents=True, exist_ok = True)
        self.path.write_text(json.dumps(self.records))
    
    def add(self, text:str, source:str, embedding:list[float])->None:
        self.records.append({
            "text": text,
            "source":source,
            "embedding": embedding
        })
    
    def search(self, query_emb:list[float], top_k: int = 3)->list[tuple[float, dict]]:
        scored = [(cosine(query_emb, r["embedding"]), r) for r in self.records]
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:top_k]