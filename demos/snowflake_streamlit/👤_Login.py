import streamlit as st
from io import StringIO
import tempfile
from cortex_agent import CortexAgent
from cortex_agent.environment_checks import is_running_in_snowflake_notebook
st.set_page_config(initial_sidebar_state='collapsed')

connection_parameters = {
    "account": "SFSEEUROPE-PROD_DEMO_GORKOW",
    "user": "ADMIN",
    "role": "ACCOUNTADMIN",
    "warehouse": "COMPUTE_WH",
    "database": "CORTEX_AGENTS_DEMO",
    "schema": "MAIN"
}

if 'agent' not in  st.session_state:
    st.title('Login')
    if is_running_in_snowflake_notebook():
        from _snowflake import get_generic_secret_string
        secret_name = st.text_input('Secret Name:')
        get_generic_secret_string('agent_api_token')
        col1, col2, col3 = st.columns(3)
        pk_button = col2.button('Private Key File', use_container_width=True)
        if pk_button:
            file = st.file_uploader('Select', accept_multiple_files=False)
            if file is not None:
                stringio = StringIO(file.getvalue().decode("utf-8"))
                pk = stringio.read()
                st.write(pk)
                #CortexAgent(private_key_file='rsa_key.p8', connection_parameters=connection_parameters)
        pat_button = col3.button('Programmatic Access Token', use_container_width=True)
        if pat_button:
            pat_text_input = st.text_input('PAT:')
        secret_button = col3.button('Secret', use_container_width=True)
    else:
        
        st.markdown('## Private Key File')
        key_file = st.file_uploader('Upload Private key', accept_multiple_files=False, type=None)
        if key_file is not None:
            temp_path = f"/tmp/{key_file.name}"
            # Save the file
            with open(temp_path, "wb") as f:
                f.write(key_file.read())
            st.session_state['agent'] = CortexAgent(private_key_file=temp_path, connection_parameters=connection_parameters)
            st.rerun()
        st.markdown('## Programmatic Access Token')
        pat_file = st.file_uploader('Upload PAT', accept_multiple_files=False, type=None)
        if pat_file is not None:
            stringio = StringIO(pat_file.getvalue().decode("utf-8"))
            string_data = stringio.read()
            st.session_state['agent'] = CortexAgent(programmatic_access_token=string_data, connection_parameters=connection_parameters)
            st.rerun()
        pat_text_input = st.text_input('PAT:')
        if pat_text_input:
            st.session_state['agent'] = CortexAgent(programmatic_access_token=pat_text_input, connection_parameters=connection_parameters)
            st.rerun()
#for chunk in agent.make_request(content='What was the total order quantity per month with status shipped?'):
#    print(chunk, end='')
else:
    st.title('You are connected!')
    if st.button('🔍 Discover Agents', use_container_width=True):
        st.switch_page("pages/1_🔍_Agent Browser.py")
    if st.button('🛠️ Create a new Agent', use_container_width=True):
        st.switch_page("pages/3_🛠️_Agent Creation.py")
    if st.button('Disconnect', use_container_width=True, type='primary'):
        del st.session_state['agent']
        st.rerun()
