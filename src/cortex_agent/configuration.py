from dataclasses import dataclass, field
import logging
from typing import Optional, List
from .tool_resources import CortexAgentToolResource, CortexAnalystService, CortexSearchService
from .tools import CortexAgentTool
from snowflake.snowpark import Session
from snowflake.snowpark.types import StructType, StructField, StringType, VariantType
from snowflake.snowpark import functions as F
from cortex_agent.tools import CortexAgentTool
import json 
import logging
logger = logging.getLogger("cortex_agent.configuration")

ALLOWED_MODELS = ['claude-3-5-sonnet','mistral-large2','llama3.3-70b','llama3.1-70b']
ALLOWED_TOOL_CHOICES = ['auto', 'required', 'tool']

@dataclass
class CortexAgentConfiguration:
    """
    Stores configuration for the Cortex Agent.

    This includes the model name, list of tools to be used, tool resources, 
    tool selection preferences, and any response instructions for the agent.

    Attributes:
        model (Optional[str]): The language model to use (default: 'claude-3-5-sonnet').
        tools (List[CortexAgentTool]): List of tool instances for processing requests.
        tool_resources (List[CortexAgentToolResource]): List of tool resource configurations.
        tool_choice (dict): Strategy for tool selection (default is auto).
        response_instruction (Optional[str]): Custom instructions for generating responses.
    """
    model: Optional[str] = 'claude-3-5-sonnet'
    tools: Optional[List[CortexAgentTool]] = field(default_factory=list)
    tool_resources: Optional[List[CortexAgentToolResource]] = field(default_factory=list)
    tool_choice: Optional[dict] = field(default_factory=lambda: {'type': 'auto'})
    response_instruction: Optional[str] = ''
    experimental: Optional[str] = field(default_factory=lambda: {})

    def set_response_instruction(self, response_instruction:str = ''):
        """
        Set the response instruction for the agent.
        
        Args:
            response_instruction (str): Response Instruction.
        
        Returns:
            None
        """ 
        self.response_instruction = response_instruction

    def add_tool(self, tool: CortexAgentTool):
        """
        Add a tool to the Cortex Agent.
        
        Args:
            tool (CortexAgentTool): The tool to add.
        
        Returns:
            None
        """
        self.tools.append(tool)
        logger.info(f"Tool {tool.name} added successfully.")

    def remove_tool(self, name: str):
        """
        Remove a tool from the Cortex Agent.
        
        Args:
            name (str): A unique identifier for the tool
        
        Returns:
            None
        """
        self.tools = [tool for tool in self.tools if tool.name != name]
        logger.info(f"Tool {name} removed successfully.")

    def add_tool_resource(self, tool_resource: CortexAgentToolResource):
        """
        Add a tool resource to the Cortex Agent.
        
        Args:
            name (str): A unique identifier for the tool resource
            resource_config (dict): Configuration for the tool resource
        
        Returns:
            None
        """
        self.tool_resources.append(tool_resource)
        logger.info(f"Tool Resource {tool_resource.resource_name} added successfully.")

    def remove_tool_resource(self, name):
        """
        Remove a tool resource from the Cortex Agent.
        
        Args:
            name (str): A unique identifier for the tool resource
        
        Returns:
            None
        """
        self.tool_resources = [resource for resource in self.tool_resources if resource.resource_name != name]
        logger.info(f"Tool Resource {name} removed successfully.")

    def set_experimental_flags(self, experimental_flags: dict):
        """
        Sets experimental flags.
        
        Args:
            experimental_flags (dict): Dictionary containings experimental flags
        
        Returns:
            None
        """
        self.experimental = experimental_flags

    def unset_experimental_flags(self):
        """
        Unsets experimental flags.
        
        Returns:
            None
        """
        self.experimental = {}

    def _get_sql_exec_tools(self):
        """
        Internal function to find all tools for SQL execution.
        
        Returns:
            None
        """
        return [tool for tool in self.tools if tool.type == 'sql_exec']
    
    def _tool_resources_to_dict(self):
        resources = {}
        for resource in self.tool_resources:
            resources[resource.resource_name] = resource.to_dict()
        return resources
    
    def save(self):
        body = {}
        body['model'] = self.model
        body['tools'] = [tool.to_dict() for tool in self.tools]
        body['tool_resources'] = self._tool_resources_to_dict()
        body['tool_choice'] = self.tool_choice
        body['response_instruction'] = self.response_instruction
        body['experimental'] = self.experimental
        return body

    def _save_to_table(self, session: Session, table: str, agent_name: str, database:str = None, schema: str = None, overwrite: bool = False, agent_description: str = ''):
        # check if agent already exists
        agent_exists = False
        full_table = [database, schema, table] if database and schema else table

        try:
            agent_exists = session.table(full_table).filter(F.col('AGENT_NAME') == agent_name).count() > 0
        except Exception as e:
            print(f"Error checking agent existence: {e}")

        # Define schema
        df_schema = StructType([
            StructField("AGENT_NAME", StringType()), 
            StructField("AGENT_DESCRIPTION", StringType()), 
            StructField("AGENT_CONFIGURATION", VariantType())
        ])

        df = session.create_dataframe([[agent_name, agent_description, self.save()]], schema=df_schema)
        df = df.with_column('CREATED_BY', F.current_user())
        df = df.with_column('CREATED_AT', F.current_timestamp())

        if not agent_exists:
            df.write.save_as_table(table_name=full_table, mode='append')
        elif agent_exists and overwrite:
            target_table = session.table(full_table)
            target_table.update({
                "AGENT_DESCRIPTION": F.lit(agent_description),
                "AGENT_CONFIGURATION": F.lit(self.save()),
                "CREATED_BY": F.current_user(),
                "CREATED_AT": F.current_timestamp()
            },
            target_table['AGENT_NAME'] == df.AGENT_NAME, df
            )
            print('Agent already exists, updating it.')
        else:
            print('Agent already exists, not overwriting it.')


    def _load_from_table(self, session: Session, table:str, agent_name:str, database:str = None, schema:str = None):
        full_table = [database, schema, table] if database and schema else table
        agents_df = session.table(full_table)
        agent_config = json.loads(agents_df.filter(F.col('AGENT_NAME') == agent_name).collect()[0]['AGENT_CONFIGURATION'])
        self.model = agent_config['model']
        self.experimental = agent_config['experimental']
        self.response_instruction = agent_config['response_instruction']
        self.tool_choice = agent_config['tool_choice']
        # convert tools to native object
        self.tools = [CortexAgentTool(tool['tool_spec']['name'], tool['tool_spec']['type'])  for tool in agent_config['tools']]
        # convert tool resources to native object
        tool_resources = []
        for tool_resource in agent_config['tool_resources']:
            if 'semantic_model_file' in agent_config['tool_resources'][tool_resource]:
                # Cortex Analyst
                tool_resources.append(CortexAnalystService(resource_name=tool_resource, **agent_config['tool_resources'][tool_resource]))
            if 'name' in agent_config['tool_resources'][tool_resource]:
                # Cortex Search Service
                tool_resources.append(CortexSearchService(resource_name=tool_resource, **agent_config['tool_resources'][tool_resource]))
        self.tool_resources = tool_resources

    def __str__(self):
        indent = "    "  # 4 spaces
        def indent_lines(items):
            return '\n'.join(f"{indent*2}{line}" for item in items for line in str(item).splitlines())

        tool_list = indent_lines(self.tools)
        resource_list = indent_lines(self.tool_resources)

        return (
            f"CortexAgentConfiguration(\n"
            f"{indent}model={self.model},\n"
            f"{indent}tools=[\n{tool_list}\n{indent}],\n"
            f"{indent}tool_resources=[\n{resource_list}\n{indent}],\n"
            f"{indent}tool_choice={self.tool_choice},\n"
            f"{indent}response_instruction={self.response_instruction!r}\n"
            f"{indent}experimental={self.experimental!r}\n"
            f")"
        )