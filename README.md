# Python API for the Snowflake Cortex Agent REST API

![PythonAPI](resources/header.png)

## Overview
A lightweight Python wrapper for the [Snowflake Cortex Agents REST API](https://docs.snowflake.com/en/user-guide/snowflake-cortex/agents), designed to simplify working with LLM-powered agents in Snowflake. Supports both sync and async workflows, streaming responses via SSE, and easy agent management.

---

## ✨ Features

- 🐍 Completely Pythonic
- 🔧 Create & configure Cortex agents
- 🔄 Prompt agents (sync and async)
- 🧵 Support for streaming responses (SSE)
- 🧰 Easy integration with Snowflake workloads
- ✅ Lightweight, no unnecessary dependencies
- ❄️ Support for Snowflake Notebooks & Streamlit in Snowflake

---

## 📦 Installation

Install via pip:

```bash
pip install cortex-agent
```

Setup the repo in Snowflake:
```sql
USE ROLE ACCOUNTADMIN;

-- Create a warehouse
CREATE WAREHOUSE IF NOT EXISTS COMPUTE_WH WITH WAREHOUSE_SIZE='X-SMALL';

-- Create a fresh Database
CREATE DATABASE IF NOT EXISTS CORTEX_AGENTS_DEMO;

-- Create the API integration with Github
CREATE OR REPLACE API INTEGRATION GITHUB_INTEGRATION_CORTEX_AGENTS_PYTHON_API
    api_provider = git_https_api
    api_allowed_prefixes = ('https://github.com/michaelgorkow/')
    enabled = true
    comment='Git integration with Michael Gorkows Github Repository.';

-- Create the integration with the Github demo repository
CREATE GIT REPOSITORY GITHUB_REPO_CORTEX_AGENTS_PYTHON_API
	ORIGIN = 'https://github.com/michaelgorkow/snowflake_cortex_agents_demo' 
	API_INTEGRATION = 'GITHUB_INTEGRATION_CORTEX_AGENTS_PYTHON_API' 
	COMMENT = 'Github Repository from Michael Gorkow with a demo for Cortex Agents.';

-- Run the installation of the Streamlit App
EXECUTE IMMEDIATE FROM @CORTEX_AGENTS_DEMO.PUBLIC.GITHUB_REPO_CORTEX_AGENTS_PYTHON_API/branches/main/setup.sql;
```

--- 

## 🚀 Quick Start
Create a new Agent that can generate and execute SQL queries, generate charts and summarizes the charts: 
```python
from cortex_agent.agent import CortexAgent
from cortex_agent.configuration import CortexAgentConfiguration
from cortex_agent.tools import SQLExecTool, DataToChartTool, CortexAnalystTool
from cortex_agent.tool_resources import CortexAnalystService

# Configure a Cortex Analyst Tool
analyst_tool = CortexAnalystTool(name='analyst1')
analyst_tool_resource = CortexAnalystService(resource_name='analyst1', semantic_model_file='@CORTEX_AGENTS_DEMO.main.semantic_models/sales_orders.yaml')
sql_exec_tool = SQLExecTool(name='sql_exec1')
data_to_chart_tool = DataToChartTool(name='datatochart1')

# Adding all tools to the Configuration
agent_config = CortexAgentConfiguration(
    model='claude-3-5-sonnet',
    tools=[analyst_tool, sql_exec_tool, data_to_chart_tool], 
    tool_resources=[analyst_tool_resource]
    )

# Create agent
agent = CortexAgent(session=session, configuration=agent_config)
for chunk in agent.make_request(content='What was the total order quantity per month with status shipped?'):
    print(chunk, end='')
```

---

## 🔐 Configuring Authentication

The `CortexAgent` class can be configured via constructor arguments.  
The following following authentication methods are supported:
| Method | Inside Snowflake | Outside Snowflake |
|:---|:---:|:---:|
| Snowpark Session | ❌ | ✅ |
| Key-pair Authentication | ✅ | ✅ |
| Programmatic Access Token | ✅ | ✅ |

To configure Key-pair authentication, follow the [documentation](https://docs.snowflake.com/en/user-guide/key-pair-auth).  
Programmatic Access Tokens are currently in PrPr.

---

## 🧠 Advanced Usage
Complete examples can be found in the following notebooks:
* [Snowflake Notebook with custom callbacks]()
* [External Notebook with custom callbacks]()

---

## 🧩 Requirements
If you want to use the API **inside of Snowflake** (e.g. in Snowflake Notebooks or Streamlit), you need to have access to or create an External Access Integration that can access your account url.  
You can create a new External Access Integration for your account like this:
```sql
CREATE OR REPLACE NETWORK RULE self_rule
  MODE = EGRESS
  TYPE = HOST_PORT
  VALUE_LIST = ('<ORG_NAME>-<ACCOUNT_NAME>.snowflakecomputing.com');

CREATE OR REPLACE EXTERNAL ACCESS INTEGRATION self_access_integration
  ALLOWED_NETWORK_RULES = (self_rule)
  ENABLED = true;
```

**SQL Exec Tool in Streamlit in Snowflake**
> [!IMPORTANT]
> To use the SQL Exec Tool in Streamlit in Snowflake, you need to use restricted caller’s rights (PrPr)
> Other tools that do not require client-side results, such as Cortex Search also work with owner rights (default).

## 📄 License
This project is licensed under the Apache License 2.0. See the [LICENSE](https://github.com/michaelgorkow/snowflake-cortex-agent-python/blob/main/LICENSE) file for details.