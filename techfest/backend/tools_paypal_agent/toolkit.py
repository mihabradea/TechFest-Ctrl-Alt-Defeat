from paypal_agent_toolkit.openai.toolkit import PayPalToolkit
from paypal_agent_toolkit.shared.configuration import Configuration, Context
import os
configuration = Configuration(
    actions={
        "orders": {
            "create": True,
            "get": True,
            "capture": True,
        }
    },
    context=Context(
        sandbox=True
    )
)

def _require(name: str) -> str:
    val = os.getenv(name)
    if not val:
        log.error("Missing env var: %s", name)
        raise RuntimeError(f"Missing env var: {name}")
    return val

# Read the SAME variables main.py uses
CLIENT_ID = _require("PAYPAL_CLIENT_ID").strip()
SECRET    = _require("PAYPAL_CLIENT_SECRET").strip()

# Initialize toolkit
toolkit = PayPalToolkit(client_id=CLIENT_ID, secret=SECRET, configuration = configuration)