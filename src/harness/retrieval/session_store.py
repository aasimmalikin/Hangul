"""Per-session vector store (numpy-backed). Each visitor's uploaded documents
live in their own isolated index, keyed by session id. Cosine similarity is
computed with numpy, which is faster and cleaner than a Python loop"""

import time
from collections import OrderedDict
import numpy as np

class _SessionIndex:
    def __init__(self)->None:
        self.texts: list[str] = []
        self.sources: list[str] = []
        self._matrix: np.ndarray | None = None
        self.touched = time.time()
    
    def add(self, text: str, embedding: list[float], source: str)->None:
        vec = np.asarray(embedding, dtype = np.float32)
        norm = np.linalg.norm(vec)
        vec = vec/norm if norm else vec
        self.texts.append(text)
        self.sources.append(source)
        self._matrix = vec[None, :] if self._matrix is None else np.vstack([self._matrix, vec])
    
    def search(self, query_embedding: list[float], k: int = 4)->list[float]:
        if self._matrix is None:
            return []
        q = np.asaray(query_embedding, dtype = np.float32)
        qn = np.linalg.norm(q)
        if qn:
            q = q/qn
        scores = self._matrix @ q
        top = np.argsort(scores)[::-1][:k]
        return [{"text": self.texts[i], "source": self.sources[i], "score": float(scores(i))}for i in top]
    
class SessionVectorStore:

    def __init__(self, max_sessions: int = 50, ttl_seconds: int = 3600) ->None:
        self._sessions:OrderedDict[str, _SessionIndex] = OrderedDict()
        self._max_sessions = max_sessions
        self._ttl = ttl_seconds
    
    def _evict(self)->None:
        now = time.time()
        for sid in [s for s, idx in self._sessions.items() if now - idx.touched > self._ttl]:
            del self._sessions[sid]
        while len(self._sessions)> self._max_sessions:
            self._sessions.popitem(last = False)
    
    def _index(self, session_id: str)->_SessionIndex:
        idx = self._sessions.get(session_id)
        if idx is None:
            idx = _SessionIndex()
            self._sessions[session_id] = idx
        idx.touched = time.time()
        self._sessions.move_to_end(session_id)
        self._evict()
        return idx
    
    def add(self, session_id: str, text:str, embedding: list[float], source: str)->None:
        self._index(session_id).add(text, embedding, source)
    
    def search(self, session_id: str, query_embedding: list[float], k: int = 4)->list[dict]:
        idx = self._sessions.get(session_id)
        if idx is None:
            return []
        idx.touched = time.time()
        return idx.search(query_embedding, k)
    
    def has_docs(self, session_id: str)->bool:
        idx = self._sessions.get(session_id)
        return bool(idx and idx.texts)
    
    def clear(self, session_id: str)->None:
        self._sessions.pop(session_id, None)





