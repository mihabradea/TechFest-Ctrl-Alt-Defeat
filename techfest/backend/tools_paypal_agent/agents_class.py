from agents import Agent
from backend.tools_paypal_agent.toolkit import toolkit

tools = toolkit.get_tools()

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