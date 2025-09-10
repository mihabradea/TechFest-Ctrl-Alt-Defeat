import gradio as gr
import os
import asyncio
from openai import OpenAI
import json
from dotenv import load_dotenv
from agents import InputGuardrailTripwireTriggered


load_dotenv(override=True)

openai_api_key = os.getenv('OPENAI_API_KEY')


from agent_config import  runner,agent

class Interface:

    def __init__(self):
        self.runner = runner
        self.agent = agent
        


    @staticmethod
    def build_transcript(history: list[dict], latest_user: str) -> str:
        """
        Convert Gradio messages history into a compact transcript for your agent.
        Gradio (type='messages') gives: [{"role": "user"|"assistant", "content": "..."}]
        """
        lines = ["[Conversation so far]"]
        for m in history:
            role = "User" if m.get("role") == "user" else "Assistant"
            content = (m.get("content") or "").strip()
            if content:
                lines.append(f"{role}: {content}")
        lines.append(f"User: {latest_user}")
        lines.append("Assistant:")
        return "\n".join(lines)

    async def respond(self, message: str, history: list[dict]):
        """
        This is the function Gradio calls every turn.
        Return a single assistant string (or a dict with role/content).
        """

        try: 
            prompt = self.build_transcript(history, message)

            result = await self.runner.run(self.agent, prompt)

            reply = getattr(result, "final_output", None) or str(result)
            return reply  
        except InputGuardrailTripwireTriggered as e:

            info = "You can't perform a request with such amount of money. Please try with a smaller amount, under 1000."
            return f"⚠️ Guardrail triggered: {info}"

    

if __name__ == "__main__":
    ui = Interface()
    gr.ChatInterface(fn=ui.respond, type="messages", title="TechFest Chat").launch()




