__version__ = '0.1'

from .agent import CortexAgent
from .tools import CortexAgentTool, CortexAnalystTool, CortexSearchTool, SQLExecTool
#from .tool_resources import CortexAgentToolResource, CortexAnalystService, CortexSearchService
from .environment_checks import is_running_in_notebook, is_running_in_snowflake_notebook
import os

# your_module/logging_config.py
import logging

def setup_module_logger(level="INFO"):
    """
    Sets up logging specifically for 'your_module' loggers only.

    Args:
        level (str or int): Logging level (e.g., "DEBUG", logging.INFO).
    """
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)

    logger = logging.getLogger("cortex_agent")  # Top-level logger for your module
    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(level)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    # Avoid passing logs to the root logger to prevent duplication or global impact
    logger.propagate = False


setup_module_logger(level='DEBUG')
logger = logging.getLogger("cortex_agent")

    
if is_running_in_notebook():
    import nest_asyncio
    nest_asyncio.apply()
    logger.info('Found interactive environment (such as a notebook). Applied nest_asyncio to correctly support async calls.')

if is_running_in_snowflake_notebook():
    import nest_asyncio
    nest_asyncio.apply()
    logger.info('Found Snowflake Notebook environment. Applied nest_asyncio to correctly support async calls.')
    
__all__ = [
    "CortexAgent",
    "CortexAgentTool",
    "CortexAnalystTool", 
    "CortexSearchTool", 
    "SQLExecTool",
    "CortexAgentToolResource",
    "CortexAnalystService", 
    "CortexSearchService"
]