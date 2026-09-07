from enum import Enum

class Tier(str, Enum):
    SAFE = "safe"
    SENSITIVE = "sensitive"
    DESTRUCTIVE = "destructive"
    ELICIT = "elicit"
    DENIED = "denied"

class Decision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    NEEDS_APPROVAL = "needs_approval"