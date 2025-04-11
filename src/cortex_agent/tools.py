import logging
from dataclasses import dataclass
from typing import Literal
import logging

logger = logging.getLogger("cortex_agent.tools")

ALLOWED_TOOL_TYPES = ['cortex_search', 'cortex_analyst_text_to_sql', 'sql_exec', 'data_to_chart']

@dataclass
class CortexAgentTool:
    """
    Represents a tool that can be utilized by the Cortex Agent to process requests.

    This base class defines a tool with a unique name and a type. Valid tool types include:
    'cortex_search', 'cortex_analyst_text_to_sql', 'sql_exec', and 'data_to_chart'.

    Attributes:
        name (str): The unique identifier for the tool.
        type (Literal): The tool type; must be one of the allowed tool types.
    """
    name: str
    type: Literal['cortex_search', 'cortex_analyst_text_to_sql', 'sql_exec', 'data_to_chart']

    def __post_init__(self):
        original_type = self.type
        normalized_type = self.type.lower()

        if original_type != normalized_type:
            logger.warning(
                f"Tool type '{original_type}' was automatically lowercased to '{normalized_type}'"
            )
            self.type = normalized_type

        if self.type not in ALLOWED_TOOL_TYPES:
            raise ValueError(
                f"Invalid tool type: '{self.type}'. Must be one of {ALLOWED_TOOL_TYPES}"
            )

    def to_dict(self) -> dict:
        """
        Converts the tool instance into a dictionary format expected by the API.

        Returns:
            dict: Dictionary representation with tool specification.
        """
        return {
            'tool_spec': {
                'type': self.type,
                'name': self.name
            }
        }
    
    def __repr__(self):
        return f"CortexAgentTool(name='{self.name}', type='{self.type}')"

@dataclass
class CortexSearchTool(CortexAgentTool):
    """
    A tool for performing search operations via Cortex Search Service.
    """
    def __init__(self, name: str):
        super().__init__(name=name, type='cortex_search')


@dataclass
class CortexAnalystTool(CortexAgentTool):
    """
    A tool designed for converting natural language questions into SQL queries via the Cortex Analyst service.
    """
    def __init__(self, name: str):
        super().__init__(name=name, type='cortex_analyst_text_to_sql')


@dataclass
class SQLExecTool(CortexAgentTool):
    """
    A tool for executing SQL queries.
    Agent will respond with this tool if there is a need to execute a SQL query.
    Actual SQL execution is happening client-side.
    """
    def __init__(self, name: str):
        super().__init__(name=name, type='sql_exec')

@dataclass
class DataToChartTool(CortexAgentTool):
    """
    A tool for converting data outputs into chart specifications.

    This tool handles the transformation of data into a Vega-Lite chart format.
    """
    def __init__(self, name: str):
        super().__init__(name=name, type='data_to_chart')