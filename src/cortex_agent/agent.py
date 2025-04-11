from dataclasses import dataclass, field
from typing import Optional
from .connection import CortexAgentConnection
from .configuration import CortexAgentConfiguration
from .api_handler import CortexAgentAPIHandler, CortexLLMAPIHandler
from snowflake.snowpark import Session
import logging
import json
from httpx_sse._models import ServerSentEvent
from .callbacks import ConversationalCallback
from .message_formats import Message
logger = logging.getLogger("cortex_agent.agent")
    
@dataclass
class CortexAgent:
    """
    Main interface for interacting with the Cortex Agent.

    This class manages the connection, API handler, and session for executing SQL
    queries through the Cortex Agent. It is the primary entry point for users to
    send requests and receive streamed responses.

    Attributes:
        configuration (CortexAgentConfiguration): Configuration parameters for the agent.
        session (Optional[Session]): An optional Snowflake session for executing SQL queries.
        private_key_file (Optional[str]): Path to the private key file for JWT authentication.
        programmatic_access_token (Optional[str]): Token for programmatic access.
        connection_parameters (Optional[dict]): Additional connection parameters.
    """
    configuration:  Optional[CortexAgentConfiguration] =  field(default_factory=CortexAgentConfiguration)
    session: Optional[Session] = None
    private_key_file: Optional[str] = None
    programmatic_access_token: Optional[str] = None
    connection_parameters: Optional[dict] = None
    #logger: logging.Logger = field(default_factory=lambda: logging.getLogger(__name__))

    def __post_init__(self):
        # set account-url, session (for SQL), token
        self.connection = CortexAgentConnection(
            session=self.session, 
            private_key_file=self.private_key_file, 
            programmatic_access_token=self.programmatic_access_token,
            connection_parameters=self.connection_parameters
            )
        
        self.api_handler = CortexAgentAPIHandler(
            connection=self.connection, 
            configuration=self.configuration
            )
        self.llm_api_handler = CortexLLMAPIHandler(
            connection=self.connection, 
            configuration=self.configuration
            )
        
    def make_request(self, content:str, callback=None):
        """
        Makes a request to the Cortex Agent and optionally uses a callback to process the response.

        Args:
            content (str): The prompt or user message.
            callback (callable): Optional function to handle response streaming.

        Yields:
            The agent's response, processed through the callback if provided.
        """
        _callback = callback if callback else ConversationalCallback(self)

        for event in self.api_handler.make_request(content=content):
            event = _callback(event)
            if hasattr(event, '__iter__') and not isinstance(event, Message):
                for part in event:
                    yield part
            else:
                yield event

    def save_to_table(self, table: str, agent_name: str, database:str = None, schema: str = None, overwrite: bool = False, agent_description: str = ''):
        """
        Saves an agent's configuration to a Snowflake table

        Args:
            table (str): Table to store agent configuration
            database (str): Database to store agent configuration
            schema (str): Schema to store agent configuration
            overwrite (bool): allow updating existing agent configuration
            agent_description (str): Description of the agent
        """
        self.configuration._save_to_table(
            session=self.connection.session, 
            table=table,
            agent_name=agent_name, 
            database=database, 
            schema=schema, 
            overwrite=overwrite, 
            agent_description=agent_description
            )
        
    def load_from_table(self, table:str, agent_name:str, database:str = None, schema:str = None):
        """
        Saves an agent's configuration to a Snowflake table

        Args:
            table (str): Table to store agent configuration
            database (str): Database to store agent configuration
            schema (str): Schema to store agent configuration
            overwrite (bool): allow updating existing agent configuration
            agent_description (str): Description of the agent
        """
        self.configuration._load_from_table(
            session=self.connection.session, 
            table=table,
            agent_name=agent_name, 
            database=database, 
            schema=schema, 
            )

    def complete(self, content:str, callback=None):
        """
        Makes a request to the Cortex Agent and optionally uses a callback to process the response.

        Args:
            content (str): The prompt or user message.
            callback (callable): Optional function to handle response streaming.

        Yields:
            The agent's response, processed through the callback if provided.
        """

        def default_callback(item):
            if isinstance(item, Message):
                return ''
            if isinstance(item, ServerSentEvent):
                item = json.loads(item.data)['choices'][0]['delta'].get('content','')
                return item
        _callback = callback if callback else default_callback

        for event in self.llm_api_handler.make_request(content=content):
            event = _callback(event)
            if hasattr(event, '__iter__') and not isinstance(event, Message) and not isinstance(event, str):
                for part in event:
                    yield part
            else:
                yield event