import os
from dotenv import load_dotenv
from paypal_agent_toolkit.openai.toolkit import PayPalToolkit
from paypal_agent_toolkit.shared.configuration import Configuration, Context
from agents import Agent, Runner, set_default_openai_key

load_dotenv()
client_id = os.getenv("PAYPAL_CLIENT_ID")
client_secret = os.getenv("PAYPAL_CLIENT_SECRET")
openai_api_key = os.getenv("OPENAI_API_KEY")


class PayPalService:
    def __init__(self):

        config = Configuration(
            actions={
                "orders": {
                    "create": True,
                    "get": True,
                    "capture": True
                }
            },
            context=Context(sandbox=True)
        )

        toolkit = PayPalToolkit(
            client_id=client_id,
            secret=client_secret,
            configuration=config
        )

        tools = toolkit.get_tools()

        set_default_openai_key(os.getenv("OPENAI_API_KEY"))

        self.agent = Agent(
            name="PayPal Agent",
            instructions="You are a helpful assistant that helps users with PayPal transactions.",
            tools=tools
        )

    def process_query(self, amount):
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        result = Runner.run_sync(self.agent, f"Create an order for ${amount}. Return the approval url and order_id")
        return result
