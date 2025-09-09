import os
import json
import openai

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


class PayPalService:

    def __init__(self, paypal_api):
        self.__load_config()

        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.openai_client = openai.Client(
            api_key=self.openai_api_key
        )

        self.paypal_api = paypal_api

    def call_model(self, messages=[]):
        """
        Handle user message and decide what actions to take
        """

        messages = [
            {
                'role': 'user',
                'content': self.__config['prompts']['system_prompt']
            },
            *messages
        ]

        MAX_ITERATIONS = 4
        for _ in range(MAX_ITERATIONS):

            response = self.openai_client.chat.completions.create(
                model="gpt-5-nano",
                messages=messages,
                tools=self.__config['prompts']['tools']
            )

            # print(f'\n\nResponse: {response}\n\n')
            # print(f'Choices: {response.choices}\n\n')

            if not hasattr(response, "choices") or not response.choices:
                raise Exception("No response from AI model")

            response_message = response.choices[0].message

            if hasattr(response_message, 'tool_calls') and response_message.tool_calls:
                tool_call = response_message.tool_calls[0]
                tool_name = tool_call.function.name
                tool_input = tool_call.function.arguments

                # print(f"Calling tool: {tool_name}")
                # print(f"Arguments: {tool_input}")

                messages.append({
                    'role': 'assistant',
                    'content': response_message.content if hasattr(response_message, 'content') else None,
                    'tool_calls': [
                        {
                            'id': tool_call.id,
                            'type': 'function',
                            'function': {
                                'name': tool_name,
                                'arguments': tool_input
                            }
                        }
                    ]
                })

                tool_response = self.__call_tool(tool_name, tool_input)

                messages.append({
                    'role': 'tool',
                    'content': str(tool_response),
                    'tool_call_id': tool_call.id
                })

                print(f"Tool response: {tool_response}")

            else:
                return response_message.content

    def __call_tool(self, tool_name, tool_input):
        match tool_name:
            case "get_invoices":
                return self.paypal_api.get_invoices()
            case "create_invoice":
                invoice_data = json.loads(tool_input)
                return self.paypal_api.create_invoice(invoice_data)
            case _:
                return f"Unknown tool: {tool_name}"

    def __load_config(self):
        with open(os.path.join(ROOT_DIR, 'config.json'), 'r') as f:
            self.__config = json.load(f)
