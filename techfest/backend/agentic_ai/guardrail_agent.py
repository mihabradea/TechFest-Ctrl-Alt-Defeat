from agents import Agent
from pydantic import BaseModel
from agents import Runner, input_guardrail, GuardrailFunctionOutput
import os
from dotenv import load_dotenv

load_dotenv(override=True)

openai_api_key = os.getenv('OPENAI_API_KEY')


class HugeAmountCheckOutput(BaseModel):
    is_huge_amount: bool
    amount: float
    currency: str

guardrail_agent = Agent( 
    name="Huge amount of money detector",
    instructions="Check if the user is mentioning any money amount. "
                 "Return is_huge_amount=True if the amount is greater than 1000. "
                 "Also return the numeric amount and the currency if mentioned.",
    output_type=HugeAmountCheckOutput,
    model="gpt-4o-mini"
)

@input_guardrail
async def guardrail_against_huge_amount(ctx, agent, message):
    result = await Runner.run(guardrail_agent, message, context=ctx.context)
    is_huge_amount = result.final_output.is_huge_amount
    return GuardrailFunctionOutput(output_info={"found_huge_amount": result.final_output}, tripwire_triggered=is_huge_amount)