from paypal_agent_toolkit.openai.toolkit import PayPalToolkit 
from paypal_agent_toolkit.shared.configuration import Configuration, Context
import os
from dotenv import load_dotenv
from agents import Agent  ,Runner

load_dotenv(override=True)

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
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

# Initialize toolkit 
toolkit = PayPalToolkit(client_id=CLIENT_ID, secret=CLIENT_SECRET, configuration = configuration)
tools = toolkit.get_tools()  


# Create agent
agent = Agent(     
    name="PayPal Assistant",     
    instructions="""     
    You're a helpful assistant specialized in managing PayPal transactions:     
    - To create orders, invoke create_order.     
    - After approval by user, invoke capture_order.     
    - To check an order status, invoke get_order_status.     
    """,     
    tools=tools 
)

runner = Runner()

def pi():
    return agent