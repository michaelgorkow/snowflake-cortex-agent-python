# Imports
import streamlit as st
import pandas as pd
st.set_page_config(layout="wide")
from snowflake.snowpark.context import get_active_session
from cortex_agent.agent import CortexAgent
from cortex_agent.configuration import CortexAgentConfiguration, ALLOWED_MODELS, ALLOWED_TOOL_CHOICES
from cortex_agent.tools import (
    CortexSearchTool, 
    CortexAnalystTool, 
    SQLExecTool,
    DataToChartTool, 
    ALLOWED_TOOL_TYPES,
    CortexAgentTool
    )
from cortex_agent.tool_resources import CortexSearchService, CortexAnalystService

from cortex_agent.configuration import CortexAgentConfiguration
from cortex_agent.tools import SQLExecTool, CortexSearchTool, CortexAnalystTool, DataToChartTool
from cortex_agent.callbacks import StreamlitCallback, StreamlitMessageHandler
from cortex_agent import setup_module_logger
import json
from cortex_agent.environment_checks import is_running_in_snowflake_notebook
import time
from snowflake.snowpark import functions as F
setup_module_logger(level='DEBUG')

DEFAULT_DB = 'CORTEX_AGENTS_DEMO'
DEFAULT_SCHEMA = 'PUBLIC'
DEFAULT_TABLE = 'MY_AGENTS'

st.title('Agent Creator')

if 'agent' not in  st.session_state:
    st.error('You need to authenticate first.')
    countdown_placeholder = st.empty()
    for i in range(5, 0, -1):
        countdown_placeholder.markdown(f"⏳ Redirecting in **{i}** seconds...")
        time.sleep(1)

    # Optional final message before redirect
    countdown_placeholder.markdown("✅ Redirecting...")
    st.switch_page('Login.py')
else:
    agent = st.session_state['agent']
    session = agent.connection.session
    agent_name = st.session_state['agent_name'] if 'agent_name' in st.session_state else ''

if 'added_tools' not in st.session_state:
    st.session_state['added_tools'] = {}

@st.cache_data(ttl='1h')
def get_search_services():
    search_services = pd.DataFrame(session.sql('SHOW CORTEX SEARCH SERVICES IN ACCOUNT').collect())
    search_services = search_services.sort_values(by=['database_name','schema_name','name'])
    return search_services

@st.cache_data(ttl='1h')
def get_semantic_models():
    stages = pd.DataFrame(session.sql('SHOW TERSE STAGES IN ACCOUNT').collect())
    stages = stages[~stages['type'].isin(['INTERNAL TEMPORARY', 'IMAGE REPOSITORY'])]
    stages = stages[['database_name','schema_name','name']]
    stages = stages.sort_values(by=['database_name','schema_name','name'])
    return stages

@st.cache_data(ttl='1h')
def get_files(database, schema, stage):
    files = session.sql(f"LS '@\"{database}\".\"{schema}\".\"{stage}\"'").filter(
        F.col('"size"') < 1000000
    ).filter(
        (F.lower(F.col('"name"')).endswith('.yaml')) | 
        (F.lower(F.col('"name"')).endswith('.yml'))
    ).select(
        F.col('"name"').alias('"File Name"'),
    ).distinct().order_by(
        ['"File Name"']
    ).to_pandas()
    return files

def add_tool_resource(toolname, tool_type, resource=None):
    if tool_type == 'cortex_search':
        search_services = get_search_services()
        event = st.dataframe(
            search_services[['database_name','schema_name','search_column','embedding_model']], 
            use_container_width=True,
            hide_index=True,
            selection_mode="single-row",
            on_select='rerun',
            key=f"{toolname}_add_search_df"
            )
        selected_service = event.selection.rows
        if len(selected_service) > 0:
            selected_search_service = search_services.iloc[selected_service].reset_index()
            database = selected_search_service['database_name'][0]
            schema = selected_search_service['schema_name'][0]
            name = selected_search_service['name'][0]
            max_results = st.number_input('Max Results:', min_value=1, max_value=100, value=5, key=f"{toolname}_add_search_max_results")
            title_column = st.selectbox('Title Column:', options=selected_search_service['columns'][0].split(','), key=f"{toolname}_add_search_title_column")
            id_column = st.selectbox('ID Column:', options=selected_search_service['columns'][0].split(','), key=f"{toolname}_add_search_id_column")
            #filter = st.text_input('Filter:', key=f"{toolname}_add_search_filter")
            help_text = f"""For Filter Syntax, see documentation:\n\n[Filter Syntax](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-search/query-cortex-search-service#filter-syntax)"""
            json_filter = '''// Rows where the "array_col" column contains "arr_value" and the "string_col" column equals "value":
{
    "@and": [
        { "@contains": { "array_col": "arr_value" } },
        { "@eq": { "string_col": "value" } }
    ]
}
            '''
            filter = st.text_area("Filter (JSON):", height=200, placeholder=json_filter, help=help_text, key=f'{toolname}_jsonfilter')

            resource = CortexSearchService(
                resource_name=toolname, 
                database=database, 
                schema=schema, 
                name=name, 
                max_results=max_results, 
                title_column=title_column, 
                id_column=id_column
                )
            return resource
    if tool_type == 'cortex_analyst_text_to_sql':
        semantic_models = get_semantic_models()
        event = st.dataframe(
            semantic_models,#[['database_name','schema_name','search_column','embedding_model']], 
            use_container_width=True,
            hide_index=True,
            selection_mode="single-row",
            on_select='rerun',
            key=f"{toolname}_add_semantic_model_df1"
            )
        selected_stage = event.selection.rows
        if len(selected_stage) > 0:
            selected_stage = semantic_models.iloc[selected_stage].reset_index()
            database = selected_stage['database_name'][0]
            schema = selected_stage['schema_name'][0]
            selected_stage_name = selected_stage['name'][0]
            files = get_files(database=database, schema=schema, stage=selected_stage_name)
            event = st.dataframe(
                files,#[['database_name','schema_name','search_column','embedding_model']], 
                use_container_width=True,
                hide_index=True,
                selection_mode="single-row",
                on_select='rerun',
                key=f"{toolname}_add_semantic_model_df2"
                )
            selected_semantic_model = event.selection.rows
            if len(selected_semantic_model) > 0:
                selected_semantic_model = files.iloc[selected_semantic_model].reset_index()
                file_name = selected_semantic_model['File Name'][0]
                #full_path = f'@\"{database}\".\"{schema}\".\"{selected_stage_name}\"/{file_name}'
                full_path = f'@\"{database}\".\"{schema}\".{file_name}'
                resource = CortexAnalystService(resource_name=toolname, semantic_model_file=full_path)
            return resource

@st.fragment
def add_tool():
    tool_name = st.text_input('Tool Name:')
    if tool_name != '':
        tool_type = st.selectbox('Type', options=ALLOWED_TOOL_TYPES, key=f"{tool_name}_add_tool_type")
        tool = CortexAgentTool(name=tool_name, type=tool_type)
        if tool_type in ['cortex_search', 'cortex_analyst_text_to_sql']:
            tool_resource = add_tool_resource(toolname=tool_name, tool_type=tool_type)
            if tool_resource is not None:# and tool_name is not '':
                col1, _, _, _ = st.columns(4)
                if col1.button('Add', use_container_width=True):
                    #st.session_state['tools'].append(tool)
                    st.session_state['added_tools'][tool_name] = {}
                    st.session_state['added_tools'][tool_name]['tool'] = tool
                    st.session_state['added_tools'][tool_name]['tool_resource'] = tool_resource
                    st.rerun()
        else:
            col1, _, _, _ = st.columns(4)
            if col1.button('Add', use_container_width=True):
                st.session_state['added_tools'][tool_name] = {}
                st.session_state['added_tools'][tool_name]['tool'] = tool
                #st.session_state['tools'].append(tool)
                st.rerun()
            return tool
    
@st.fragment
def edit_tool(existing_tool):
    old_tool_name = existing_tool['tool'].name
    tool_name = existing_tool['tool'].name
    tool_type = existing_tool['tool'].type
    tool_name = st.text_input('Tool Name:', value=tool_name)
    tool_type = st.selectbox('Type', options=ALLOWED_TOOL_TYPES, index=ALLOWED_TOOL_TYPES.index(tool_type), key=f'{tool_name}_edit_tool_type')
    tool = CortexAgentTool(name=tool_name, type=tool_type)
    if tool_type in ['cortex_search', 'cortex_analyst_text_to_sql']:
        tool_resource = add_tool_resource(toolname=tool_name, tool_type=tool_type, resource=existing_tool['tool_resource'])
        col1, col2, _, _ = st.columns(4)
        if col1.button('Update', use_container_width=True, key=f'{tool_name}_update_btn'):
            st.session_state['added_tools'][tool_name] = {}
            st.session_state['added_tools'][tool_name]['tool'] = tool
            st.session_state['added_tools'][tool_name]['tool_resource'] = tool_resource
            if old_tool_name != tool_name:
                del st.session_state['added_tools'][old_tool_name]
            st.rerun()
        if col2.button('Delete', use_container_width=True, type='primary', key=f'{tool_name}_delete_btn'):
            del st.session_state['added_tools'][old_tool_name]
            st.rerun()
    else:
        col1, col2, _, _ = st.columns(4)
        if col1.button('Update', use_container_width=True, key=f'{tool_name}_update_btn'):
            st.session_state['added_tools'][tool_name] = tool_name
            st.session_state['added_tools'][tool_name]['tool'] = tool
            if old_tool_name != tool_name:
                del st.session_state['added_tools'][old_tool_name]
            st.rerun()
        if col2.button('Delete', use_container_width=True, type='primary', key=f'{tool_name}_delete_btn'):
            del st.session_state['added_tools'][old_tool_name]
            st.rerun()

def update_agent():
    tool_list = [st.session_state['added_tools'][t]['tool'] for t in st.session_state['added_tools']]
    tool_resource_list = [st.session_state['added_tools'][t]['tool_resource'] for t in st.session_state['added_tools'] if 'tool_resource' in st.session_state['added_tools'][t]]
    
    agent.configuration.model = model
    agent.configuration.tool_choice = tool_choice
    agent.configuration.response_instruction = response_instruction
    agent.configuration.tools = tool_list
    agent.configuration.tool_resources = tool_resource_list
    st.session_state['agent'] = agent
    st.session_state['agent_name'] = agent_name

agent_name = st.text_input('Agent Name:', value=agent_name)
if agent_name != '':
    col1, col2 = st.columns(2)
    model = col1.selectbox('Model:', ALLOWED_MODELS, index=ALLOWED_MODELS.index(agent.configuration.model))
    tool_choice = col2.selectbox('Tool Choice:', ALLOWED_TOOL_CHOICES, ALLOWED_TOOL_CHOICES.index(agent.configuration.tool_choice['type']))
    if tool_choice in ['auto','required']:
        tool_choice = {'type':tool_choice}
    response_instruction = st.text_area('Response Instruction:', value='', height=100)

    #experimental = 
    st.write('---')
    st.markdown('## Add Tools:')
    if st.button('Add Tool'):
        with st.expander('**New Tool**', expanded=True):
            add_tool()

    st.write('---')
    # TODO display existing tools if loaded from hub
    st.markdown('## Available Tools:')
    for tool in st.session_state['added_tools']:
        with st.expander(f"**{tool}** [{st.session_state['added_tools'][tool]['tool'].type}]", expanded=False):
            edit_tool(st.session_state['added_tools'][tool])

    st.write('---')
    col1, col2, _, _ = st.columns(4)
    if col1.button('Create / Update Agent', use_container_width=True):
        update_agent()

    if col2.button('Save Agent to Table', use_container_width=True):
        from functions import save_dialog
        update_agent()
        save_dialog()