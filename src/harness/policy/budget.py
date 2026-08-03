class Budget:
    def __init__(self, max_steps: int = 8, max_tokens: int = 50_000)->None:
        self.max_steps = max_steps
        self.max_tokens = max_tokens
        self.steps = 0
        self.tokens = 0
    
    def add(self, *, steps: int = 0, tokens: int = 0)->None:
        self.steps += steps
        self.tokens += tokens
    
    def exceeded(self)->str | None:
        if self.steps > self.max_steps:
            return f"Exceeded max steps: {self.steps} > {self.max_steps}"
        if self.tokens > self.max_tokens:
            return f"Exceeded max tokens: {self.tokens} > {self.max_tokens}"
        return None
    

