from dataclasses import dataclass, field, asdict
from typing import Optional
import logging

logger = logging.getLogger("cortex_agent.tool_resources")

@dataclass
class CortexAgentToolResource:
    """
    Base class for configuring a resource associated with a Cortex Agent tool.

    Attributes:
        resource_name (str): The unique identifier for the resource.
    """
    resource_name: str

    def to_dict(self) -> dict:
        """
        Converts the resource configuration into a dictionary, excluding the resource name.
        
        Returns:
            dict: Dictionary representation of the resource configuration.
        """
        attrs = {k: v for k, v in asdict(self).items() if v is not None and k != 'resource_name'}
        return attrs
    
    def __repr__(self):
        attrs = {k: v for k, v in asdict(self).items() if v is not None}
        return f"{self.__class__.__name__}({attrs})"

    def __str__(self):
        parts = [f"  {k} = {v!r}" for k, v in asdict(self).items()]
        return f"{self.__class__.__name__}(\n" + "\n".join(parts) + "\n)"

@dataclass(repr=False)
class CortexAnalystService(CortexAgentToolResource):
    """
    Configuration for a Cortex Analyst service used to translate text to SQL.

    This class constructs a semantic model file reference based on provided database,
    schema, stage, and file parameters if a specific semantic model file is not supplied.

    Attributes:
        semantic_model_file (Optional[str]): File reference for the semantic model.
        database (Optional[str]): Database name.
        schema (Optional[str]): Schema name.
        stage (Optional[str]): Stage name.
        file (Optional[str]): File name used for building the semantic model file reference.
    """
    semantic_model_file: Optional[str] = None
    database: Optional[str] = None
    schema: Optional[str] = None
    stage: Optional[str] = None
    file: Optional[str] = None

    def __post_init__(self):
        if not self.semantic_model_file:
            if self.database and self.schema and self.stage and self.file:
                self.semantic_model_file = f"@{self.database}.{self.schema}.{self.stage}/{self.file}"
            else:
                raise ValueError(
                    "Either 'semantic_model_file' or all of 'database', 'schema', 'stage', and 'file' must be provided."
                )
    def to_dict(self) -> dict:
        attrs = {k: v for k, v in asdict(self).items() if k == 'semantic_model_file'}
        return attrs


@dataclass(repr=False)
class CortexSearchService(CortexAgentToolResource):
    """
    Configuration for a Cortex Search service.

    This class defines the parameters required to configure a search service, such as 
    database, schema, service name, and search-specific options like maximum results.

    Attributes:
        name (Optional[str]): Unique name for the search service.
        database (Optional[str]): Database name.
        schema (Optional[str]): Schema name.
        service_name (Optional[str]): Service name.
        max_results (Optional[int]): Maximum number of results to retrieve.
        title_column (Optional[str]): Column name used as the title in search results.
        id_column (Optional[str]): Column name used as the identifier in search results.
        filter (dict): Additional filters to apply during search.
    """
    name: Optional[str] = None
    database: Optional[str] = None
    schema: Optional[str] = None
    service_name: Optional[str] = None

    max_results: Optional[int] = None
    title_column: Optional[str] = None
    id_column: Optional[str] = None
    filter: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.name:
            if self.database and self.schema and self.service_name:
                self.name = f"{self.database}.{self.schema}.{self.service_name}"
            else:
                raise ValueError(
                    "Either 'name' or all of 'database', 'schema', and 'service_name' must be provided."
                )