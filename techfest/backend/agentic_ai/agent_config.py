from paypal_agent_toolkit.openai.toolkit import PayPalTool,PayPalAPI,PayPalToolkit
from paypal_agent_toolkit.shared.configuration import Configuration, Context
import os
from dotenv import load_dotenv
from agents import Agent, Runner
from techfest.backend.agentic_ai.guardrail_agent import guardrail_against_huge_amount

from agents import FunctionTool
load_dotenv(override=True)
from techfest.backend.agentic_ai.invoices.configuration import Configuration
from typing import List

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
openai_api_key = os.getenv('OPENAI_API_KEY')
import techfest.backend.agentic_ai.invoices.tools as invoice_tools


configuration = Configuration(     
    actions={         
        "orders": {            
            "create": True,             
            "get": True,             
            "capture": True,         
        },
         "products": {
            "create": True,
            "list": True,
            "show": True
        },
        "invoices": {
            "create": True,
            "get": True,
            "list": True,
            "send": True,
            "sendReminder": True,
            "cancel": True,
            "generateQRC": True,
        }
    },     
    context=Context(         
        sandbox=True     
    ) 
)  

_paypal_api = PayPalAPI(client_id=CLIENT_ID, secret=CLIENT_SECRET, context=configuration.context)

toolkit = PayPalToolkit(client_id=CLIENT_ID, secret=CLIENT_SECRET, configuration = configuration)
tools = toolkit.get_tools()  

# Initialize toolkit 
# toolkit = PayPalToolkit(client_id=CLIENT_ID, secret=CLIENT_SECRET, configuration = configuration)
# tools = toolkit.get_tools()  
# print(f"Initialized {len(tools)} PayPal tools.")
# print(tools)

def get_tools() -> List[FunctionTool]:
        """Get the tools in the openai agent."""
        return [PayPalTool(_paypal_api,t) for t in invoice_tools.tools]

# Create agent
agent = Agent(     
    name="PayPal Assistant",     
    instructions="""     
    You're a helpful assistant specialized in managing PayPal transactions:     
    - To create orders, invoke create_order.     
    - After approval by user, invoke capture_order.     
    - To check an order status, invoke get_order_status.  

    Don't make any action and tool call unless the user explicitly confirm it. Always give a action final review and then ask for confirmation.
    """,     
    tools=tools,
    input_guardrails=[guardrail_against_huge_amount]
)

runner = Runner()
