import streamlit as st
import json
from cortex_agent.message_formats import AgentAPIRequest, AgentAPIResponse
from cortex_agent.callbacks import StreamlitMessageHandler
import time
st.title('Agent History')

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

message_handler = StreamlitMessageHandler(agent)
content = st.container()
with st.sidebar:
    if st.button('Show API Calls & Responses', use_container_width=True):
        for i, api_call in enumerate(agent.api_handler.api_history):
            if isinstance(api_call, AgentAPIRequest):
                with content.chat_message('user'):
                    with st.expander(f"RequestHeader_{i}", expanded=False):
                        st.write(api_call.header)
                    st.write(api_call.body)
            if isinstance(api_call, AgentAPIResponse):
                with content.chat_message('ai'):
                    if api_call.event.event == "message.delta":
                        with st.expander(f"ResponseHeader_{i}", expanded=False):
                            st.write(dict(api_call.header))
                        data = json.loads(api_call.event.data)
                        st.write(data)
                    if api_call.event.event == "done":
                        with st.expander(f"ResponseHeader_{i}", expanded=False):
                            st.write(dict(api_call.header))
                        st.write(api_call.event.data)
            content.write('---')
    if st.button('Show Message History', use_container_width=True):
        for message in agent.api_handler.message_history:
            with content:
                message_handler(message)
                st.write('---')