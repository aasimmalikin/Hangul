from harness.policy.tiers import Tier, Decision

class ToolPolicy:
    def __init__(self, tiers: dict[str, Tier], default: Tier = Tier.SENSITIVE):
        self._tiers = tiers
        self._default = default
    
    def tier_of(self, tool_name:str)->Tier:
        return self._tiers.get(tool_name, self._default)
    
    def decide(self, tool_name:str)->Decision:
        tier = self.tier_of(tool_name)
        if tier in (Tier.SAFE, Tier.SENSITIVE):
            return Decision.ALLOW
        if tier == Tier.DESTRUCTIVE:
            return Decision.NEEDS_APPROVAL
        return Decision.DENY