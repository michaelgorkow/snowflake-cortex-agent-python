import copy
from typing import List, Any, Dict, Union
from dataclasses import dataclass
from .connection import CortexAgentConnection
from .configuration import CortexAgentConfiguration
from .message_formats import Message, UserResult, AgentAPIHistory, AgentMessageHistory, format_events_for_message_history, format_events_for_llm_message_history
from httpx_sse._models import ServerSentEvent
from httpx import AsyncClient
from httpx_sse import aconnect_sse
import asyncio
from typing import Generator
import json
import pandas as pd
import logging
from queue import SimpleQueue
import threading
logger = logging.getLogger("cortex_agent.api_handler")

class CortexAgentAPIHandler:
    """
    Handles API interactions with the Cortex Agent.

    This class builds the necessary request headers and body, manages asynchronous 
    communication with the Cortex Agent API (including Server-Sent Events streaming),
    and integrates SQL execution if requested by the agent.

    Attributes:
        connection (CortexAgentConnection): Connection details for authentication and API URL.
        configuration (CortexAgentConfiguration): The configuration containing model, tools, and instructions.
        api_history (AgentAPIHistory): History of API requests and responses.
        message_history (AgentMessageHistory): History of messages exchanged with the agent.
    """
    def __init__(self, connection: CortexAgentConnection, configuration: CortexAgentConfiguration):
        self.connection = connection
        self.configuration = configuration
        self.api_history = AgentAPIHistory()
        self.message_history = AgentMessageHistory()

    def _build_request(self):
        headers = {}
        if self.connection.programmatic_access_token:
            headers['Authorization'] = f"Bearer {self.connection.programmatic_access_token}"
        elif self.connection.jwt_token:
            headers['Authorization'] = f"Bearer {self.connection.jwt_token}"
        elif self.connection.snowflake_token:
            headers['Authorization'] = f'Snowflake Token="{self.connection.snowflake_token}"'
        headers['Content-Type'] = "application/json"
        headers['Accept'] = "text/event-stream"

        body = {}
        body['model'] = self.configuration.model
        body['tools'] = [tool.to_dict() for tool in self.configuration.tools]
        body['tool_resources'] = self._tool_resources_to_dict()
        body['tool_choice'] = self.configuration.tool_choice
        body['response_instruction'] = self.configuration.response_instruction
        body['messages'] = list(self.message_history.format_for_agent_call())
        return headers, body
    
    def _tool_resources_to_dict(self):
        resources = {}
        for resource in self.configuration.tool_resources:
            resources[resource.resource_name] = resource.to_dict()
        return resources
    

    async def _make_async_request(self, headers:dict, body:dict):
        self.api_history.add(header=headers, event=body)
        all_events_from_response = []
        logger.debug(f"""
            Making request with the following data:
            URL: https://{self.connection.account_url}{self.connection.API_ENDPOINT}
            Header: {headers}
            Body: {body}"""
        )
        async with AsyncClient(timeout=None) as client:
            async with aconnect_sse(
                client,
                method="POST",
                url=f'https://{self.connection.account_url}{self.connection.API_ENDPOINT}',
                json=body,
                headers=headers
            ) as event_source:
                if event_source.response.status_code == 200:
                    async for event in event_source.aiter_sse():
                        yield event # yielding SSE
                        self.api_history.add(header=event_source.response.headers, event=event)
                        all_events_from_response.append(event)
                else:
                    error_text = await event_source.response.aread()
                    raise Exception(f"Agent got a bad API response: {event_source.response.status_code} - {error_text.decode()}")
                events_for_message_history = format_events_for_message_history(all_events_from_response)
                message = Message(role='assistant', content=events_for_message_history)
                self.message_history.add(message)

    def _check_if_sql_execution_requested(self):
        sql_tool_name = None
        sql_tool_use_id = None
        sql_statement = None
        try:
            last_message = json.loads(self.api_history[-2].event.data)['delta']['content'][-1]
            if last_message['type'] == 'tool_use':
                if last_message['tool_use']['name'] in [tool.name for tool in self.configuration._get_sql_exec_tools()]:
                    sql_tool_name = last_message['tool_use']['name']
                    sql_tool_use_id = last_message['tool_use']['tool_use_id']
                    sql_statement = last_message['tool_use']['input']['query'].replace('\n',' ')
        except:
            pass
        return sql_tool_name, sql_tool_use_id, sql_statement
    
    def make_request(self, content, role:str = None) -> Generator:
        """
        Sends a message to the agent and yields streamed responses.

        Args:
            content (str or UserResult): Input content to send to the agent.
            role (str): The role of the message sender, typically 'user'.

        Yields:
            Event data or processed output depending on the agent's response.
        """
        # Add wrapper function to provide a synchronous interface
        return self._sync_request_wrapper(content, role)

    def _sync_request_wrapper(self, content, role:str = None) -> Generator:
        """Wrapper to convert async operations to a synchronous generator."""
        if not role:
            message = Message(role='user', content=content)
            self.message_history.add(message)
        elif role == 'user':
            message = Message(role='user', content=content)
            self.message_history.add(message)

        headers, body = self._build_request()
        
        # Create event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Create the queue and run the async task
        queue = asyncio.Queue()

        yield message
        task = loop.create_task(self._async_request_to_queue(headers, body, queue))
        
        # Yield items as they become available
        try:
            while True:
                try:
                    item = loop.run_until_complete(queue.get())
                    if item is None:  # Signal for end of stream
                        break
                    yield item
                except asyncio.CancelledError:
                    break
        
        finally:
            # Check for SQL execution after completing the stream
            sql_tool_name, sql_tool_use_id, sql_statement = self._check_if_sql_execution_requested()
            if sql_statement:
                query = self.connection.session.sql(sql_statement).collect(block=False)
                while not query.is_done():
                    logger.info('Still executing SQL Query ...')
                query_results = UserResult(
                    tool_name=sql_tool_name, 
                    tool_use_id=sql_tool_use_id, 
                    query_id=query.query_id, 
                    query_df=pd.DataFrame(query.result())
                )
                # Use yield from to delegate to another generator
                yield from self.make_request(role='user', content=query_results)

    async def _async_request_to_queue(self, headers, body, queue):
        """Process async requests and put results into the provided queue."""
        try:
            async for event in self._make_async_request(headers, body):
                await queue.put(event)
        except Exception as e:
            logger.error(f"Error during async request: {e}")
            # Optionally put the exception in the queue to be raised in the main thread
            await queue.put(e)
        finally:
            # Signal end of stream
            await queue.put(None)

class CortexLLMAPIHandler:
    """
    Handles API interactions with the Cortex Complete (LLM Access).

    This class builds the necessary request headers and body, manages asynchronous 
    communication with the Cortex Agent API (including Server-Sent Events streaming).

    Attributes:
        connection (CortexAgentConnection): Connection details for authentication and API URL.
        configuration (CortexAgentConfiguration): The configuration containing model, tools, and instructions.
        api_history (AgentAPIHistory): History of API requests and responses.
        message_history (AgentMessageHistory): History of messages exchanged with the complete() function.
    """
    def __init__(self, connection: CortexAgentConnection, configuration: CortexAgentConfiguration):
        self.connection = connection
        self.configuration = configuration
        self.api_history = AgentAPIHistory()
        self.message_history = AgentMessageHistory()

    def _build_request(self):
        headers = {}
        if self.connection.programmatic_access_token:
            headers['Authorization'] = f"Bearer {self.connection.programmatic_access_token}"
        elif self.connection.jwt_token:
            headers['Authorization'] = f"Bearer {self.connection.jwt_token}"
        elif self.connection.snowflake_token:
            headers['Authorization'] = f'Snowflake Token="{self.connection.snowflake_token}"'
        headers['Content-Type'] = "application/json"
        headers['Accept'] = 'Accept: application/json, text/event-stream'

        body = {}
        body['model'] = self.configuration.model
        body['top_p'] = 0
        body['temperature'] = 0
        body['messages'] = self.message_history.format_for_llm_call()
        return headers, body
    
    async def _make_async_request(self, headers:dict, body:dict):
        self.api_history.add(header=headers, event=body)
        all_events_from_response = []
        async with AsyncClient(timeout=None) as client:
            async with aconnect_sse(
                client,
                method="POST",
                url=f'https://{self.connection.account_url}/api/v2/cortex/inference:complete',
                json=body,
                headers=headers
            ) as event_source:
                if event_source.response.status_code == 200:
                    async for event in event_source.aiter_sse():
                        yield event # yielding SSE
                        self.api_history.add(header=event_source.response.headers, event=event)
                        all_events_from_response.append(event)
                else:
                    error_text = await event_source.response.aread()
                    raise Exception(f"Agent got a bad API response: {event_source.response.status_code} - {error_text.decode()}")
                events_for_message_history = format_events_for_llm_message_history(all_events_from_response)
                message = Message(role='assistant', content=events_for_message_history)
                self.message_history.add(message)

    def make_request(self, content, role:str = None) -> Generator:
        """
        Sends a message to the agent and yields streamed responses.

        Args:
            content (str or UserResult): Input content to send to the agent.
            role (str): The role of the message sender, typically 'user'.

        Yields:
            Event data or processed output depending on the agent's response.
        """
        # Add wrapper function to provide a synchronous interface
        return self._sync_request_wrapper(content, role)

    def _sync_request_wrapper(self, content, role:str = None) -> Generator:
        if not role:
            message = Message(role='user', content=content)
            self.message_history.add(message)

        headers, body = self._build_request()
        
        # Create event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Create the queue and run the async task
        queue = asyncio.Queue()

        yield message
        task = loop.create_task(self._async_request_to_queue(headers, body, queue))
        
        # Yield items as they become available
        while True:
            try:
                item = loop.run_until_complete(queue.get())
                if item is None:  # Signal for end of stream
                    break
                yield item
            except asyncio.CancelledError:
                break

    async def _async_request_to_queue(self, headers, body, queue):
        """Process async requests and put results into the provided queue."""
        try:
            async for event in self._make_async_request(headers, body):
                await queue.put(event)
        except Exception as e:
            logger.error(f"Error during async request: {e}")
            # Optionally put the exception in the queue to be raised in the main thread
            await queue.put(e)
        finally:
            # Signal end of stream
            await queue.put(None)
