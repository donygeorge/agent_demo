from dotenv import load_dotenv
import chainlit as cl
import base64
from agents.planning_agent import PlanningAgent
from agents.implementation_agent import ImplementationAgent
from agents.supervisor_agent import SupervisorAgent
from prompts import PLANNING_PROMPT, SYSTEM_PROMPT

load_dotenv()

# Note: If switching to LangSmith, uncomment the following, and replace @observe with @traceable
# from langsmith.wrappers import wrap_openai
# from langsmith import traceable
# client = wrap_openai(openai.AsyncClient())

from langfuse.decorators import observe
from langfuse.openai import AsyncOpenAI
 
client = AsyncOpenAI()

gen_kwargs = {
    "model": "gpt-4o",
    "temperature": 0.2
}

# Create an instance of the Agent class
planning_agent = PlanningAgent(client=client)
implementation_agent = ImplementationAgent(client=client)
planning_agent.register_agent(implementation_agent)
implementation_agent.register_agent(planning_agent)
supervisor_agent = SupervisorAgent(client=client)
supervisor_agent.register_agent(planning_agent)
supervisor_agent.register_agent(implementation_agent)

@observe
@cl.on_chat_start
def on_chat_start():    
    message_history = [{"role": "system", "content": SYSTEM_PROMPT}]
    cl.user_session.set("message_history", message_history)

@observe
async def generate_response(client, message_history, gen_kwargs):
    response_message = cl.Message(content="")
    await response_message.send()

    stream = await client.chat.completions.create(messages=message_history, stream=True, **gen_kwargs)
    async for part in stream:
        if token := part.choices[0].delta.content or "":
            await response_message.stream_token(token)
    
    await response_message.update()

    return response_message

@cl.on_message
@observe
async def on_message(message: cl.Message):
    message_history = cl.user_session.get("message_history", [])
    # Processing images exclusively
    images = [file for file in message.elements if "image" in file.mime] if message.elements else []

    if images:
        # Read the first image and encode it to base64
        with open(images[0].path, "rb") as f:
            base64_image = base64.b64encode(f.read()).decode('utf-8')
        message_history.append({
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": message.content
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}"
                    }
                }
            ]
        })
    else:
        message_history.append({"role": "user", "content": message.content})
    
    appended_messsages = await supervisor_agent.execute(message_history)

    message_history.extend(appended_messsages)
    # message_history.append({"role": "assistant", "content": response_message})
    cl.user_session.set("message_history", message_history)

if __name__ == "__main__":
    cl.main()
