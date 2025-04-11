import os

def is_running_in_notebook():
    """
    Returns True if the code is running in an interactive notebook environment
    such as Jupyter, VSCode notebooks, or Google Colab.

    Check is done to conditionally apply nest_asyncio.
    """
    try:
        from IPython import get_ipython
        shell = get_ipython().__class__.__name__
        return shell in ('ZMQInteractiveShell', 'GoogleShell')
    except (NameError, ImportError):
        return False
    
def is_running_in_snowflake_notebook():
    """
    Returns True if the code is running in an interactive snowflake notebook environment.

    Check is done to conditionally apply nest_asyncio and format account-url.
    """
    return os.environ.get("CONDA_PREFIX", "").startswith("/usr/lib/python_udf/")

def is_running_inside_streamlit():
    """
    Check whether the current Python code is running inside a Streamlit app context.

    This function uses Streamlit's internal runtime API to determine if the code 
    is being executed within a proper Streamlit execution context (i.e., launched 
    via `streamlit run ...`). It returns False if Streamlit is being run in 
    "bare mode" (e.g., from a Jupyter notebook or interactive shell), where the 
    `ScriptRunContext` is not available.

    Returns:
        bool: True if running inside a Streamlit app, False otherwise.
    """
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        return get_script_run_ctx() is not None
    except Exception:
        return False