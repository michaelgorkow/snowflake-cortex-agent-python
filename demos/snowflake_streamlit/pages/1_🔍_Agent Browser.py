# Imports
import streamlit as st
import pandas as pd
st.set_page_config(layout="wide")
from snowflake.snowpark.context import get_active_session
from cortex_agent.agent import CortexAgent
from cortex_agent.configuration import CortexAgentConfiguration
from cortex_agent.tools import (
    CortexSearchTool, 
    CortexAnalystTool, 
    SQLExecTool,
    DataToChartTool
    )
from cortex_agent.tool_resources import CortexSearchService, CortexAnalystService

from cortex_agent.configuration import CortexAgentConfiguration
from cortex_agent.tools import SQLExecTool, CortexSearchTool, CortexAnalystTool, DataToChartTool
from cortex_agent.callbacks import StreamlitCallback, StreamlitMessageHandler
from cortex_agent import setup_module_logger
import json
from cortex_agent.environment_checks import is_running_in_snowflake_notebook
import time
from functions import get_table_picker
setup_module_logger(level='DEBUG')

DEFAULT_DB = 'CORTEX_AGENTS_DEMO'
DEFAULT_SCHEMA = 'PUBLIC'
DEFAULT_TABLE = 'MY_AGENTS'

st.title('Agent Browser')

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

def get_default_index(options, element):
    options = list(options)
    try:
        index = options.index(element)
    except ValueError:
        index = 0  # or any fallback
    return index

with st.sidebar:
    if False:
        st.markdown('### Select Agent Table')
        all_tables = get_all_tables()
        available_databases = list(all_tables['database_name'].unique())
        default_db_index = get_default_index(available_databases, DEFAULT_DB)
        database = st.selectbox('Database:', options=available_databases, index=default_db_index)
        available_schemas = list(all_tables[all_tables['database_name'] == database]['schema_name'].unique())
        default_schema_index = get_default_index(available_schemas, DEFAULT_SCHEMA)
        schema = st.selectbox('Schema:', options=available_schemas, index=default_schema_index)
        available_tables = list(all_tables[(all_tables['database_name'] == database) & (all_tables['schema_name'] == schema)]['name'].unique())
        default_table_index = get_default_index(available_tables, DEFAULT_TABLE)
        table = st.selectbox('Schema:', options=available_tables, index=default_table_index)
    database, schema, table = get_table_picker()

agents = session.table([database,schema,table]).to_pandas()

if 'AGENT_NAME' in agents.columns:
    cols = st.columns(4)
    for i, row in agents.iterrows():
        col_index = i % 4
        with cols[col_index]:
            with st.container(border=True):
                st.markdown(f"<div style='text-align: center;'><h3>🤖 {row['AGENT_NAME']}</h3></div>", unsafe_allow_html=True)
                st.markdown(f"🧑‍💻&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<b>{row['CREATED_BY']}</b>", unsafe_allow_html=True)
                formatted = row['CREATED_AT'].strftime("%Y-%m-%d %H:%M")
                st.markdown(f"📅&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<b>{formatted}</b>", unsafe_allow_html=True)
                config = json.loads(row['AGENT_CONFIGURATION'])
                st.markdown(f"🧠&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<b>{config['model']}</b>", unsafe_allow_html=True)
                st.markdown(f"<i>{row['AGENT_DESCRIPTION']}</i>", unsafe_allow_html=True)
                tools = config['tools']
                for tool in tools:
                    tool = tool['tool_spec']
                    sql_exec_names = [tool["tool_spec"]["name"] for tool in tools if tool["tool_spec"]["type"] == "sql_exec"]
                    data_to_chart_names = [tool["tool_spec"]["name"] for tool in tools if tool["tool_spec"]["type"] == "data_to_chart"]
                    analyst_names = [tool["tool_spec"]["name"] for tool in tools if tool["tool_spec"]["type"] == "cortex_analyst_text_to_sql"]
                    search_names = [tool["tool_spec"]["name"] for tool in tools if tool["tool_spec"]["type"] == "cortex_search"]
                for tool in analyst_names:
                    name = tool
                    color = '#2E86C1'
                    type_ = 'Analyst'
                    st.markdown(
                        f"""
                        <div style='padding: 6px 12px; margin: 6px 0; border-radius: 8px; background-color: #F2F3F4; display: flex; justify-content: space-between; align-items: center;'>
                            <span style='font-weight: bold;'>{name}</span>
                            <span style='background-color: {color}; color: white; padding: 4px 8px; border-radius: 6px; font-size: 12px; width: 80px; display: inline-block; text-align: center;'>{type_}</span>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                for tool in search_names:
                    name = tool
                    color = '#27AE60'
                    type_ = 'Search'
                    st.markdown(
                        f"""
                        <div style='padding: 6px 12px; margin: 6px 0; border-radius: 8px; background-color: #F2F3F4; display: flex; justify-content: space-between; align-items: center;'>
                            <span style='font-weight: bold;'>{name}</span>
                            <span style='background-color: {color}; color: white; padding: 4px 8px; border-radius: 6px; font-size: 12px; width: 80px; display: inline-block; text-align: center;'>{type_}</span>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                for tool in sql_exec_names:
                    name = tool
                    color = '#CA6F1E'
                    type_ = 'SQL'
                    st.markdown(
                        f"""
                        <div style='padding: 6px 12px; margin: 6px 0; border-radius: 8px; background-color: #F2F3F4; display: flex; justify-content: space-between; align-items: center;'>
                            <span style='font-weight: bold;'>{name}</span>
                            <span style='background-color: {color}; color: white; padding: 4px 8px; border-radius: 6px; font-size: 12px; width: 80px; display: inline-block; text-align: center;'>{type_}</span>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                for tool in data_to_chart_names:
                    name = tool
                    color = '#8E44AD'
                    type_ = 'Charts'
                    st.markdown(
                        f"""
                        <div style='padding: 6px 12px; margin: 6px 0; border-radius: 8px; background-color: #F2F3F4; display: flex; justify-content: space-between; align-items: center;'>
                            <span style='font-weight: bold;'>{name}</span>
                            <span style='background-color: {color}; color: white; padding: 4px 8px; border-radius: 6px; font-size: 12px; width: 80px; display: inline-block; text-align: center;'>{type_}</span>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                st.write('---')
                col1, col2 = st.columns(2)
                with col1:
                    if st.button(f"Load", key=f"btn_load_{i}", use_container_width=True):
                        agent.load_from_table(database=database, table=table, schema=schema, agent_name=row['AGENT_NAME'])
                        st.session_state['agent_name'] = row['AGENT_NAME']
                        st.switch_page('pages/2_💬_Agent Chat.py')
                        st.rerun()
                with col2:
                    if st.button(f"Explore", key=f"btn_explore_{i}", use_container_width=True):
                        st.write('X')
else:
    st.error('This is not a table with agent configurations.')