class MemoryCache:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}
    async def get(self, key: str) -> str | None:
        return self._store.get(key)
    
    async def set(self, key:str, value:str) -> None:
        self._store[key] = value
