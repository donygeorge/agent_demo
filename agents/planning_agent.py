from agents.base_agent import Agent 
from prompts import PLANNING_PROMPT

class PlanningAgent(Agent):
    
    def __init__(self, client, gen_kwargs=None):
        super().__init__(name="planning", client=client, prompt=PLANNING_PROMPT, gen_kwargs=gen_kwargs)
        # Add any additional initialization specific to PlanningAgent