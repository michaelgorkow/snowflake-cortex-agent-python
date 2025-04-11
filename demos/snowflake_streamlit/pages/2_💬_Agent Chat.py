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
from cortex_agent.api_handler import AgentAPIHistory, AgentMessageHistory
import time
setup_module_logger(level='DEBUG')

st.title('Agent Chat')

if 'agent' not in st.session_state:
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

    with st.sidebar:
        if st.button('Reset Agent Chat', use_container_width=True):
            agent.api_handler.message_history = AgentMessageHistory()
            agent.api_handler.api_history = AgentAPIHistory()


    streamlit_message_handler = StreamlitMessageHandler(agent)

    for message in agent.api_handler.message_history:
        streamlit_message_handler(message)
                
    if prompt := st.chat_input("What was the total order quantity per month with status shipped?"):
        for chunk in agent.make_request(content=prompt, callback=StreamlitCallback(agent)):
            pass