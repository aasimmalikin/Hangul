import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field

@dataclass
class Span:
    name: str
    span_id: str
    start: float
    end: float | None = None
    attributes: dict = field(default_factory = dict)
    status: str = "ok"

    @property
    def duration_ms(self)->float:
        return round(((self.end or time.time())-self.start)*1000, 1)

@dataclass
class Trace:
    trace_id: str
    spans: list[Span] = field(default_factory = list)

    @contextmanager
    def span(self, name:str, **attributes):
        s = Span(name = name, span_id = uuid.uuid4().hex[:8], start = time.time(), attributes = dict(attributes))
        self.spans.append(s)
        try:
            yield s
        except Exception:
            s.status = "Error"
            s.end = time.time()
            raise
        else:
            s.end = time.time()
        
    def summary(self)->dict:
        model_spans = [s for s in self.spans if s.name =="gen_ai.chat"]
        tool_spans = [s for s in self.spans if s.name =="gen_ai.tool.execute"]
        return {
            "trace_id": self.trace_id,
            "total_ms": round(sum(s.duration_ms for s in self.spans if s.name =="agent.run"),1),
            "model_calls": len(model_spans),
            "tool_calls": len(tool_spans),
            "input_tokens": sum(s.attributes.get("gen_ai.usage.input_tokens", 0)for s in model_spans),
            "output_tokens": sum(s.attributes.get("gen_ai.usage.output_tokens", 0)for s in model_spans),
            "errors": [s.name for s in self.spans if s.status == "error"]

        }

PRICING = {"gpt-4o-mini": (0.15, 0.60), "gpt-4o": (2.50, 10.00)}

def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    pin, pout = PRICING.get(model, (0.0, 0.0))
    return round(input_tokens / 1_000_000 * pin + output_tokens / 1_000_000 * pout, 6)


