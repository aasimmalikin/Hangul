"""The ask_user tool: how the agent requests a decision from the human.

This tool is never actually executed. Its purpose is to PAUSE the run -- the
policy classifies it at a tier that requires approval, so the loop halts and
stores it as pending."""

from harness.tools.base import Tool

async def ask_user(question: str, options: list[dict])-> str:
    return "[awaiting user choice]"

ASK_USER_TOOL = Tool(
    name = "ask_user",
    description = ("Ask the user to choose between 2-4 concrete options. Use it only "
        "when the request is genuinely ambiguous, the ambiguity changes the answer, "
        "and it cannot be settled from context, memory, or by searching with the "
        "other tools -- fill routine gaps with a stated assumption instead. This "
        "pauses the run until the user answers, so asking should be rare. Give each "
        "option a short label and a one-line description of what choosing it means "
        "for the answer, so the user can decide without asking you to explain."),

    parameter = {
        "type": "object",
        "properties": {
            "question": {"type": "string"},
            "options": {
                "type": "array",
                "minItems": 2,
                "maxItems": 4,
                "items": {
                    "type": "object",
                    "properties": {
                        "label": {"type": "string",
                                  "description": "The choice itself, a few words."},
                        "description": {"type": "string",
                                        "description": "One line on what this choice means."},
                    },
                    "required": ["label", "description"],
                },
            },
        },
        "required": ["question", "options"],
    },
    handler = ask_user
)
