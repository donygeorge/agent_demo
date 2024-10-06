from agents.base_agent import Agent, pretty_print_messages
from prompts import SUPERVISOR_PROMPT
import chainlit as cl
import json

class SupervisorAgent(Agent):
    
    def __init__(self, client, gen_kwargs=None):
        super().__init__(name="supervisor", client=client, prompt=SUPERVISOR_PROMPT, gen_kwargs=gen_kwargs)
        # Add any additional initialization specific to SupervisorAgent
        
    async def handle_call_agent(self, tool_calls, message_history):
        appended_messages = []
        contain_call_agent = False
        copied_message_history = message_history.copy()
        
        for tool_call in tool_calls:
            function_name = tool_call["name"]
            arguments = tool_call["arguments"]

            # print(f"DEBUG: function_name: {function_name}")
            # print(f"DEBUG: arguments: {arguments}")        
            
            if function_name == "callAgent":
                arguments_dict = json.loads(arguments)
                agent_name = arguments_dict.get("agent_name")
                agent_message = arguments_dict.get("message")
                if agent_name and agent_name in self.known_agents:
                    contain_call_agent = True

                    call_message = cl.Message(content=agent_message)
                    await call_message.send()

                    # Inform the user about the agent call
                    print(f"DEBUG: calling {agent_name} agent with message: {agent_message}")
                    call_message = cl.Message(content=f"Calling the {agent_name.capitalize()} Agent...")
                    await call_message.send()

                    message = {"role": "user", "content": f'[from SUPERVISOR agent]: {agent_message}'}
                    copied_message_history.append(message)
                    appended_messages.append(message)

                    # Execute the called agent
                    call_agent_messages = await self.known_agents[agent_name].execute(copied_message_history)
                    print(f"\n\nDEBUG: response from call_agent_messages:\n {pretty_print_messages(call_agent_messages)}\n\n")
                    appended_messages.extend(call_agent_messages)
                    
                    # Inform the user about the completion of the agent call
                    complete_message = cl.Message(content=f"The {agent_name.capitalize()} Agent has completed its task.")
                    await complete_message.send()

        return contain_call_agent, appended_messages
    
    async def execute(self, message_history):
        print(f'executing supervisor execute')
        appended_messages = []
        while True:
            full_response, tool_calls = await self.extract_response(message_history)
        
            text_response = {"role": "assistant", "content": full_response}
            message_history.append(text_response)

            update_artifact_appended_messages = await self.handle_update_artifact(tool_calls)
            appended_messages.extend(update_artifact_appended_messages)
            
            print(f"\nDEBUG (supervisor): Original message_history:\n {pretty_print_messages(message_history)}\n\n")
            contain_call_agent, call_appended_messages = await self.handle_call_agent(tool_calls, message_history)
            print(f"\nDEBUG (supervisor): response from call:\n {pretty_print_messages(call_appended_messages)}\n\n")
            appended_messages.extend(call_appended_messages)
            message_history.extend(call_appended_messages)
            print(f"\nDEBUG (supervisor): Updated message_history:\n {pretty_print_messages(message_history)}\n\n")
    
            if not contain_call_agent:
                final_message = cl.Message(content="The web page creation process is complete.")
                await final_message.send()
                return appended_messages

    
            # # Check if the process is complete
            # if "<<PROCESS COMPLETE>>" in response:
            #     final_message = cl.Message(content="The web page creation process is complete.")
            #     await final_message.send()
            #     return appended_messages
                                            
