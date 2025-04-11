import streamlit as st
import pandas as pd
import time

DEFAULT_DB = 'CORTEX_AGENTS_DEMO'
DEFAULT_SCHEMA = 'PUBLIC'
DEFAULT_TABLE = 'MY_AGENTS'

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


@st.cache_data(ttl='1h')
def get_all_tables(refresh_key=None):
    return pd.DataFrame(session.sql('SHOW TERSE TABLES IN ACCOUNT').collect())

def get_default_index(options, element):
    options = list(options)
    try:
        index = options.index(element)
    except ValueError:
        index = 0  # or any fallback
    return index

def get_table_picker(refresh_key=None):
    st.markdown('### Select Agent Table')
    all_tables = get_all_tables(refresh_key)
    available_databases = list(all_tables['database_name'].unique())
    default_db_index = get_default_index(available_databases, DEFAULT_DB)
    database = st.selectbox('Database:', options=available_databases, index=default_db_index)
    available_schemas = list(all_tables[all_tables['database_name'] == database]['schema_name'].unique())
    default_schema_index = get_default_index(available_schemas, DEFAULT_SCHEMA)
    schema = st.selectbox('Schema:', options=available_schemas, index=default_schema_index)
    available_tables = list(all_tables[(all_tables['database_name'] == database) & (all_tables['schema_name'] == schema)]['name'].unique())
    default_table_index = get_default_index(available_tables, DEFAULT_TABLE)
    table = st.selectbox('Schema:', options=available_tables, index=default_table_index)
    return database, schema, table

@st.dialog(title='Save Agent to table')
def save_dialog():
    database, schema, table = get_table_picker()
    agent = st.session_state['agent']
    agent_name = st.session_state['agent_name']
    agent_description = st.text_area('Agent Description:', height=100)
    if st.button('Save'):
        agent.save_to_table(database=database, schema=schema, table=table, agent_name=agent_name, agent_description=agent_description)
        st.rerun()