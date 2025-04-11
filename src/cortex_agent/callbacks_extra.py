import streamlit as st
import json
import hashlib
from cortex_agent.environment_checks import is_running_inside_streamlit

def make_cache_key(*args, **kwargs) -> str:
    try:
        # Serialize args and kwargs in a stable way
        key_data = {
            "args": args,
            "kwargs": kwargs
        }
        key_str = json.dumps(key_data, sort_keys=True, default=str)
    except TypeError:
        # Fallback if something isn't serializable
        key_str = str((args, kwargs))
    
    return "response_cache_" + hashlib.sha256(key_str.encode()).hexdigest()

def generate_chart_summary(agent, user_prompt: str, chart_spec: dict):
    """
    Generate summaries given vega-lite chart-specs.

    Keyword Args:
        agent (CortexAgent): Whether to display tool usage information.
        user_prompt (str): Whether to display tool results.
        chart_spec (bool): vega-lite chart-spec retrieved from Agent.
    """

    prompt = f"""
    You are given a vega-lite spec that has been generated based on this user question and available Snowflake data: 
    {user_prompt}
    
    Summarize what the user can see in the chart based on the question and the spec.
    Only respond with the summary of the data and the plot. Don't explain you used the vega-lite spec for your answer.

    Make sure to apply the following formatting:
    * Use markdown styling to form your answers if required. Ensure the markdown is valid. Do not use a multi-line quotes (e.g. ```).
    * Ensure text links are valid markdown.
    
    The vega-lite-spec:
    {chart_spec}
    """
    if is_running_inside_streamlit():
        # only use st.session_state if running in Streamlit
        cache_key = make_cache_key(content=prompt)
        if cache_key in st.session_state:
            for chunk in st.session_state[cache_key]:
                safe_chunk = chunk.replace("$", "\\$")
                yield safe_chunk
        else:
            chunks = []
            for chunk in agent.complete(content=prompt):
                safe_chunk = chunk.replace("$", "\\$")
                chunks.append(safe_chunk)
                yield safe_chunk
            st.session_state[cache_key] = chunks
    else:
        # if not using streamlit, cache responses in agent object
        cache_key = make_cache_key(content=prompt)
        if not hasattr(agent, '_chart_summaries'):
            agent._chart_summaries = {}
        if cache_key in  agent._chart_summaries:
            for chunk in agent._chart_summaries[cache_key]:
                safe_chunk = chunk.replace("$", "\\$")
                yield safe_chunk
        else:
            chunks = []
            for chunk in agent.complete(content=prompt):
                safe_chunk = chunk.replace("$", "\\$")
                chunks.append(safe_chunk)
                yield safe_chunk
            agent._chart_summaries[cache_key] = chunks