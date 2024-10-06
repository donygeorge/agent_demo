import os
import json
import chainlit as cl

class Agent:
    """
    Base class for all agents.
    """

    tools = [
        {
            "type": "function",
            "function": {
                "name": "updateArtifact",
                "description": "Update an artifact file which is HTML, CSS, or markdown with the given contents.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "The name of the file to update.",
                        },
                        "contents": {
                            "type": "string",
                            "description": "The markdown, HTML, or CSS contents to write to the file.",
                        },
                    },
                    "required": ["filename", "contents"],
                    "additionalProperties": False,
                },
            }
        },
        {
            "type": "function",
            "function": {
            "name": "callAgent",
            "description": "Call another agent to perform a specific task with instructions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "agent_name": {
                        "type": "string",
                        "description": "The name of the agent to call (e.g., 'implementation').",
                    },
                    "message": {
                        "type": "string",
                        "description": "Instructions or message to pass to the called agent.",
                    },
                },
                "required": ["agent_name", "message"],
                "additionalProperties": False,
                }
            }
        }
    ]

    known_agents = {}

    def __init__(self, name, client, prompt="", gen_kwargs=None):
        self.name = name
        self.client = client
        self.prompt = prompt
        self.gen_kwargs = gen_kwargs or {
            "model": "gpt-4o",
            "temperature": 0.2
        }
        
    def register_agent(self, agent):
        self.known_agents[agent.name] = agent

    async def extract_response(self, message_history):
        """
        Executes the agent's main functionality.

        Note: probably shouldn't couple this with chainlit, but this is just a prototype.
        """
        copied_message_history = message_history.copy()

        # Check if the first message is a system prompt
        if copied_message_history and copied_message_history[0]["role"] == "system":
            # Replace the system prompt with the agent's prompt
            copied_message_history[0] = {"role": "system", "content": self._build_system_prompt()}
        else:
            # Insert the agent's prompt at the beginning
            copied_message_history.insert(0, {"role": "system", "content": self._build_system_prompt()})

        response_message = cl.Message(content="")
        await response_message.send()

        print("\n\nDEBUG: Message history sent to LLM: " + pretty_print_messages(copied_message_history))
        stream = await self.client.chat.completions.create(messages=copied_message_history, stream=True, tools=self.tools, tool_choice="auto", **self.gen_kwargs)

        full_response = ""
        tool_calls = []
        current_tool_call_index = None
        current_tool_call = None
        
        async for part in stream:
            delta = part.choices[0].delta
            
            if delta.content:
                await response_message.stream_token(delta.content)
                full_response += delta.content

            if delta.tool_calls:
                is_tool_call = True
                # print("Tool calls: " + str(delta.tool_calls))
                for tool_call in delta.tool_calls:
                    if tool_call.index is not current_tool_call_index:  # A new tool call is starting
                        if current_tool_call:
                            tool_calls.append(current_tool_call)
                        current_tool_call = {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments or ""
                        }
                        current_tool_call_index = tool_call.index
                    else:
                        if tool_call.function and tool_call.function.arguments:
                            current_tool_call["arguments"] += tool_call.function.arguments
                        elif tool_call.function and tool_call.function.name:
                            current_tool_call["name"] += tool_call.function.name

        if current_tool_call:
            tool_calls.append(current_tool_call)
            
        # backfill tool calls if none are returned and LLM return text that looks like a tool call
        if len(tool_calls) == 0:
            if "agent_name" in full_response and "message" in full_response:
                print("DEBUG: Content that looks like a tool call: " + full_response)
                tool_calls.append({
                    "name": "callAgent",
                    "arguments": full_response
                })
                full_response = ""
                print("Filled in tool call from response text")
                
        print("Tool calls: [" + self.name + "]: " + str(tool_calls)) 
        truncated_response = full_response[:100] + "..." if len(full_response) > 100 else full_response
        print("full_response: " + self.name + ":" + truncated_response)
        print("\n\n==================================================\n\n")

        return full_response, tool_calls
        
    async def handle_update_artifact(self, tool_calls):
        appended_messages = []
        for tool_call in tool_calls:
            function_name = tool_call["name"]
            arguments = tool_call["arguments"]

            # print(f"DEBUG: function_name: {function_name}")
            # print(f"DEBUG: arguments: {arguments}")        
            
            if function_name == "updateArtifact":              
                arguments_dict = json.loads(arguments)
                filename = arguments_dict.get("filename")
                print(f"DEBUG: updating filename: {filename}")
                contents = arguments_dict.get("contents")
                
                if filename and contents:
                    os.makedirs("artifacts", exist_ok=True)
                    with open(os.path.join("artifacts", filename), "w") as file:
                        file.write(contents)
                    
                    # # Add a message to the message history
                    system_message = {
                        "role": "system",
                        "content": f"The artifact '{filename}' was updated."
                    }
                    appended_messages.append(system_message)
                    # message_history.append(system_message)
                    
                    # Inform the user about the file update
                    print(f"DEBUG: updating message: The file '{filename}' has been updated.")
                    update_message = cl.Message(content=f"The file '{filename}' has been updated.")
                    await update_message.send()

                    # stream = await self.client.chat.completions.create(messages=message_history, stream=True, **self.gen_kwargs)
                    # async for part in stream:
                    #     if token := part.choices[0].delta.content or "":
                    #         await response_message.stream_token(token)  
        
        return appended_messages

    async def execute(self, message_history):
        print("executing base agent execute")
        full_response, tool_calls = await self.extract_response(message_history)
        appended_messages = []
        
        text_response = {"role": "assistant", "content": f'[from \'{self.name} agent\'] : {full_response}'}
        appended_messages.append(text_response)
        
        update_artifact_appended_messages = await self.handle_update_artifact(tool_calls)
        appended_messages.extend(update_artifact_appended_messages)
        
        print(f"\n\nDEBUG: appended_messages in base agent:\n {pretty_print_messages(appended_messages)}\n\n")
        print(f"\n\nDEBUG: full_response in base agent:\n {full_response}\n\n")
        
        return appended_messages

    def _build_system_prompt(self):
        """
        Builds the system prompt including the agent's prompt and the contents of the artifacts folder.
        """
        artifacts_content = "<ARTIFACTS>\n"
        artifacts_dir = "artifacts"

        if os.path.exists(artifacts_dir) and os.path.isdir(artifacts_dir):
            for filename in os.listdir(artifacts_dir):
                file_path = os.path.join(artifacts_dir, filename)
                if os.path.isfile(file_path):
                    with open(file_path, "r") as file:
                        file_content = file.read()
                        artifacts_content += f"<FILE name='{filename}'>\n{file_content}\n</FILE>\n"
        
        artifacts_content += "</ARTIFACTS>"

        return f"{self.prompt}\n{artifacts_content}"
    
def pretty_print_messages(messages, max_chars=150):
    pretty_messages = []
    for msg in messages:
        role = msg.get('role', 'unknown')
        content = msg.get('content', '')
        
        if isinstance(content, list):
            # If content is a list, join its elements
            content = ' '.join(str(item) for item in content)
        elif not isinstance(content, str):
            # If content is neither a list nor a string, convert it to a string
            content = str(content)
            
        # Replace newline characters with spaces
        content = content.replace('\n', ' ')
        
        truncated_content = content[:max_chars] + ('...' if len(content) > max_chars else '')
        pretty_messages.append(f"{role}: {truncated_content}")
    return "\n".join(pretty_messages)

    