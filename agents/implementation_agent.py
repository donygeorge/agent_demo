from agents.base_agent import Agent
from prompts import IMPLEMENTATION_PROMPT

class ImplementationAgent(Agent):
    
    def __init__(self, client, gen_kwargs=None):
        super().__init__(name="implementation", client=client, prompt=IMPLEMENTATION_PROMPT, gen_kwargs=gen_kwargs)
        # Add any additional initialization specific to ImplementationAgent

    def execute(self, message_history):
        print(f'executing implementation agent execute')
        return super().execute(message_history)