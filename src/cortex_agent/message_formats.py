from dataclasses import dataclass, field
from collections.abc import MutableMapping
from typing import List, Any, Dict, Union
import json
from httpx_sse._models import ServerSentEvent
import copy
import pandas as pd
import logging

logger = logging.getLogger("cortex_agent.message_formats")

class Message(MutableMapping):
    """
    Represents a structured message exchanged with the Cortex Agent.

    Supports both user and assistant roles and handles multiple content types
    such as plain text, tool results, and server-sent events.

    Attributes:
        role (str): The role of the message sender ('user' or 'assistant').
        content (Any): The content of the message, structured as a list of dictionaries.
    """
    def __init__(self, role: str, content: Any):
        self._data = {}
        self._data['role'] = role

        if role == 'user' and isinstance(content, str):
            self._data['content'] = [{
                'type': 'text',
                'text': content
            }]

        elif role == 'user' and hasattr(content, 'to_dict'):
            self._data['content'] = [content.to_dict()]

        elif role == 'assistant' and isinstance(content, list):
            self._data['content'] = content

        elif role == 'assistant' and isinstance(content, str):
            self._data['content'] = [{
                'type': 'text',
                'text': content
            }]

        elif role == 'assistant' and isinstance(content, ServerSentEvent):
            self._data['content'] = [{
                'type': 'ServerSentEvent',
                'data': content.data
            }]

    # Required methods for MutableMapping
    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        self._data[key] = value

    def __delitem__(self, key):
        del self._data[key]

    def __iter__(self):
        return iter(self._data)

    def __len__(self):
        return len(self._data)

    def __repr__(self):
        role = repr(self._data.get('role'))
        content = repr(self._data.get('content'))
        return f"Message(role={role}, content={content})"

    def to_dict(self):
        return self._data

    def to_json(self, **kwargs):
        return json.dumps(self._data, **kwargs)

class UserResult:
    """
    Wraps the result of a SQL exeuction from a user to be sent as a message.

    Attributes:
        query_id (str): Query ID from of the executed SQL query
        tool_name (str): name of the sql_exec tool
        tool_use_id(str): id of the sql_exec tool
        query_df (pd.DataFrame): pandas Dataframe with query results
    """
    def __init__(self, query_id: str, tool_name: str, tool_use_id: str, query_df:pd.DataFrame):
        self.content = dict()
        self.content['type'] = 'tool_results'
        self.content['tool_results'] = dict()
        self.content['tool_results']['name'] = tool_name
        self.content['tool_results']['tool_use_id'] = tool_use_id
        self.content['tool_results']['content'] = [dict()]
        self.content['tool_results']['content'][0]['type'] = 'json'
        self.content['tool_results']['content'][0]['json'] = dict()
        self.content['tool_results']['content'][0]['json']['query_id'] = query_id
        self.content['tool_results']['content'][0]['json']['query_df'] = query_df

    def to_dict(self):
        return self.content
    

@dataclass
class AgentAPIResponse:
    """
    Represents an API response event from the Cortex Agent.

    Attributes:
        header (dict): The response header details.
        event (List[ServerSentEvent]): The event or events received in the response.
    """
    header: dict  
    event: List[ServerSentEvent]

@dataclass
class AgentAPIRequest:
    """
    Represents an API request event sent to the Cortex Agent.

    Attributes:
        header (dict): The request header details.
        body (List[Dict]): The body payload of the API request.
    """
    header: dict  
    body: List[Dict]

class AgentAPIHistory:
    """
    Maintains a history of API requests and responses exchanged with the Cortex Agent.

    This is used for debugging and to reconstruct the conversation context for later API calls.
    """
    def __init__(self):
        self.messages: List[AgentAPIResponse] = []

    def add(self, header: dict, event: Union[ServerSentEvent,Dict]):
        if isinstance(event, ServerSentEvent):
            self.messages.append(AgentAPIResponse(header=copy.deepcopy(header), event=event))
        if isinstance(event, dict):
            self.messages.append(AgentAPIRequest(header=copy.deepcopy(header), body=event))

    def __iter__(self):
        return iter(self.messages)
    
    def __getitem__(self, index):
        return self.messages[index]
    
    def __str__(self):
        if not self.messages:
            return "[]"
        return "[\n  " + ",\n  ".join(str(message) for message in self.messages) + "\n]"

    def __repr__(self):
        if not self.messages:
            return "[]"
        return "[\n  " + ",\n  ".join(repr(message) for message in self.messages) + "\n]"
    
class AgentMessageHistory:
    """
    Maintains a history of messages exchanged with the Cortex Agent.

    This history is used to reconstruct the conversation context for subsequent API calls,
    and it supports formatting of messages by removing non-serializable elements (like DataFrames).
    """
    def __init__(self):
        self.messages: List[Message] = []

    def add(self, message):
        self.messages.append(message.to_dict())

    def __iter__(self):
        return iter(self.messages)
    
    def __getitem__(self, index):
        return self.messages[index]
    
    def __str__(self):
        if not self.messages:
            return "[]"
        return "[\n  " + ",\n  ".join(str(message) for message in self.messages) + "\n]"

    def __repr__(self):
        if not self.messages:
            return "[]"
        return "[\n  " + ",\n  ".join(repr(message) for message in self.messages) + "\n]"
    
    def format_for_agent_call(self):
        # remove dataframes before calling API
        messages = copy.deepcopy(self.messages)
        for message in messages:
            if message['role'] == 'user':
                if message['content'][0].get('tool_results'):
                    if 'query_df' in message['content'][0]['tool_results']['content'][0]['json']:
                        del message['content'][0]['tool_results']['content'][0]['json']['query_df']
        return messages
    
    def format_for_llm_call(self):
        # complete endpoint expects different structure
        formatted_messages = []
        for message in self.messages:
            formatted_messages.append({'role':message['role'], 'content':message['content'][0]['text']})
        return formatted_messages
    
def format_events_for_message_history(events):
    messages = []
    text_response = ''
    for event in events:
        if event.event == 'message.delta':
            data = json.loads(event.data)
            content = data.get('delta')
            content = content['content']
            if content:
                if content[0]['type'] == 'text':
                    text_response += content[0]['text']
                else:
                    messages.extend(content)
        if event.event == 'done':
            pass
    if text_response != '':
        messages.append({'type':'text', 'text':text_response})
    return messages

def format_events_for_llm_message_history(events):
    messages = []
    text_response = ''
    for event in events:
        if event.event == 'message':
            data = json.loads(event.data)
            if 'content' in data['choices'][0]['delta']:
                content = data['choices'][0]['delta']['content']
                text_response += content
    if text_response != '':
        messages.append({'type':'text', 'text':text_response})
    return messages