from typing import Union
from httpx_sse._models import ServerSentEvent
#from .agent import CortexAgent
from cortex_agent.message_formats import Message
import json
import pandas as pd
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown
from rich.syntax import Syntax
from .environment_checks import is_running_in_snowflake_notebook
import streamlit as st
import pandas as pd
from typing import Union
from httpx_sse._models import ServerSentEvent
import time
from cortex_agent.callbacks_extra import generate_chart_summary
import logging
logger = logging.getLogger("cortex_agent.callbacks")

console = Console()
panel_padding = (1,1)
outer_panel_padding = (0,1)

def df_to_rich_table(df: pd.DataFrame) -> Table:
    table = Table(header_style="bold black")
    for col in df.columns:
        table.add_column(str(col))
    for _, row in df.iterrows():
        table.add_row(*map(str, row))
    return table

class ConsoleCallback:
    """
    Callback for printing agent responses to the console using Rich.

    This callback processes different types of messages (user prompts, tool uses,
    tool results, charts, and text responses) and displays them in a formatted way
    using panels, tables, and markdown.

    Keyword Args:
        display_tool_use (bool): Whether to display tool usage information.
        display_tool_results (bool): Whether to display tool results.
        display_charts (bool): Whether to display charts.
        console_print (bool): Whether to print directly to the console or yield the output.
        panel_padding (tuple): Padding for inner panels.
        outer_panel_padding (tuple): Padding for outer panels.
        enable_markdown (bool): Whether to render text as markdown.
        (Other display_* flags control display behavior for specific tool types.)
    """
    def __init__(self, agent, **kwargs):
        self.agent = agent

        # Turn on/off results
        self.display_tool_use = kwargs.get('display_tool_use', True)
        self.display_tool_use_sql = kwargs.get('display_tool_use_sql', True)
        self.display_tool_use_search = kwargs.get('display_tool_use_search', True)
        self.display_tool_use_sql_exec = kwargs.get('display_tool_use_sql_exec', True)
        self.display_tool_use_data_to_chart = kwargs.get('display_tool_use_data_to_chart', True)
        self.display_tool_results = kwargs.get('display_tool_results', True)
        self.display_tool_results_search_results = kwargs.get('display_tool_results_search_results', True)
        self.display_tool_results_sql = kwargs.get('display_tool_results_sql', True)
        self.display_tool_results_data = kwargs.get('display_tool_results_data', True)
        self.display_tool_results_chart = kwargs.get('display_tool_results_chart', False)
        self.display_charts = kwargs.get('display_charts', True)
        self.display_text_results = kwargs.get('display_text_results', True)
        self.summarize_charts = kwargs.get('summarize_charts', True)

        # markdown and padding for rich panels
        self.panel_padding = kwargs.get('panel_padding', (1,1))
        self.outer_panel_padding = kwargs.get('outer_panel_padding', (1,1))
        self.enable_markdown = kwargs.get('enable_markdown', True)

        # Return text or immediately print it
        self.console_print = kwargs.get('console_print', True)

        # fixed variables
        self.analyst_service_names = [tool.name for tool in agent.configuration.tools if tool.type == 'cortex_analyst_text_to_sql']
        self.search_service_names = [tool.name for tool in agent.configuration.tools if tool.type == 'cortex_search']
        self.sql_exec_names = [tool.name for tool in agent.configuration.tools if tool.type == 'sql_exec']
        self.data_to_chart_names = ['data_to_chart'] # always data_to_chart #[tool.name for tool in agent.configuration.tools if tool.type == 'data_to_chart']
        self.console = Console()
        self.text_output = ''
        self.last_tool_name = None # temporary bugfix, since tool_results.name is empty for Cortex Search
        self.user_prompt = ''

        if is_running_in_snowflake_notebook():
            # console print not supported in snowflake notebooks
            self.console_print = False

    def __call__(self, message: Union[Message, ServerSentEvent]):
        if isinstance(message, Message):
            if message['role'] == 'user':
                if message['content'][0]['type'] == 'text':
                    text = message['content'][0]['text']
                    self.user_prompt = text
                    text_panel = Panel(text, title=f"[bold black]User Prompt:", padding=self.outer_panel_padding)
                    if self.console_print:
                        console.print(text_panel)
                    else:
                        with console.capture() as capture:
                            console.print(text_panel)
                        yield capture.get()

                if message['content'][0]['type'] == 'tool_results':
                    if self.display_tool_results_data:
                        tool_name = message['content'][0]['tool_results']['name']
                        query_id = message['content'][0]['tool_results']['content'][0]['json']['query_id']
                        df = message['content'][0]['tool_results']['content'][0]['json']['query_df']
                        sql_result_panel = Panel(df_to_rich_table(df), title=f"[bold black]SQL Results (Query-ID:{query_id})", padding=self.panel_padding)
                        if self.console_print:
                            console.print(sql_result_panel)
                        else:
                            with console.capture() as capture:
                                console.print(sql_result_panel)
                            yield capture.get()
        if isinstance(message, ServerSentEvent):
            event = message
            if event.event == "done":
                if self.text_output != '':
                    if self.enable_markdown:
                        self.text_output = Markdown(self.text_output)
                    text_panel = Panel(self.text_output, title=f"[bold black]Text response:", padding=self.outer_panel_padding)
                    if self.console_print:
                        console.print(text_panel)
                    else:
                        with console.capture() as capture:
                            console.print(text_panel)
                        yield capture.get()
                    self.text_output = ''
            if event.event == "message.delta":
                data = json.loads(event.data)
                if "delta" in data and "content" in data["delta"]:
                    for content in data['delta']['content']:

                        if content['type'] == 'tool_use':
                            if self.display_tool_use:
                                if self.display_tool_use_sql:
                                    if content['tool_use']['name'] in self.analyst_service_names:
                                        tool_use_content = []

                                        for m in content['tool_use']['input'].get('messages',''):
                                            tool_use_content.append(f"Input: {m}")
                                        if content['tool_use']['input'].get('model') is not None:
                                            tool_use_content.append(f"Model: {content['tool_use']['input'].get('model')}")
                                        inner_panel = Panel("\n".join(tool_use_content), title="[bold black]Tool Input", padding=self.panel_padding)
                                        outer_panel = Panel(inner_panel, title=f"[bold black]Tool Use: {content['tool_use']['name']}", padding=self.outer_panel_padding)
                                        if self.console_print:
                                            console.print(outer_panel)
                                        else:
                                            with console.capture() as capture:
                                                console.print(outer_panel)
                                            yield capture.get()
                                
                                if content['tool_use']['name'] in self.search_service_names:
                                    if self.display_tool_use_search:
                                        tool_use_content = []
                                        tool_use_content.append(f"Query: {content['tool_use']['input'].get('query')}")
                                        tool_use_content.append(f"Filters: {content['tool_use']['input'].get('filters')}")
                                        tool_use_content.append(f"Limit: {content['tool_use']['input'].get('limit')}")
                                        tool_use_content.append(f"Columns: {content['tool_use']['input'].get('columns')}")
                                        inner_panel = Panel("\n".join(tool_use_content), title="[bold black] Tool Input", padding=self.panel_padding)
                                        outer_panel = Panel(inner_panel, title=f"[bold black]Tool Use: {content['tool_use']['name']}", padding=self.outer_panel_padding)
                                        if self.console_print:
                                            console.print(outer_panel)
                                        else:
                                            with console.capture() as capture:
                                                console.print(outer_panel)
                                            yield capture.get()
                                        # temporary bugfix
                                        self.last_tool_name = content['tool_use']['name']

                                if content['tool_use']['name'] in self.sql_exec_names:
                                    if self.display_tool_use_sql_exec:
                                        sql = Syntax(content['tool_use']['input']['query'], "sql", theme="monokai", line_numbers=True)
                                        inner_panel = Panel(sql, title="[bold black]Tool Input", padding=self.panel_padding)
                                        outer_panel = Panel(inner_panel, title=f"[bold black]Tool Use: {content['tool_use']['name']}", padding=self.outer_panel_padding)
                                        if self.console_print:
                                            console.print(outer_panel)
                                        else:
                                            with console.capture() as capture:
                                                console.print(outer_panel)
                                            yield capture.get()
                                
                                if content['tool_use']['name'] in  self.data_to_chart_names:
                                    if self.display_tool_use_data_to_chart:
                                        tool_use_content = []
                                        for m in content['tool_use']['input'].get('messages',''):
                                            tool_use_content.append(f"Input: {m}")
                                        if content['tool_use']['input'].get('model') is not None:
                                            tool_use_content.append(f"Model: {content['tool_use']['input'].get('model')}")
                                        inner_panel = Panel("\n".join(tool_use_content), title="[bold black]Tool Input", padding=self.panel_padding)
                                        outer_panel = Panel(inner_panel, title=f"[bold black]Tool Use: {content['tool_use']['name']}", padding=self.outer_panel_padding)
                                        if self.console_print:
                                            console.print(outer_panel)
                                        else:
                                            with console.capture() as capture:
                                                console.print(outer_panel)
                                            yield capture.get()

                        if content['type'] == 'tool_results':
                            if self.display_tool_results:
                                #if content['tool_results']['name'] in self.search_service_names:
                                if content['tool_results']['name'] in self.search_service_names or self.last_tool_name in self.search_service_names:
                                    if self.display_tool_results_search_results:
                                        for tool_result in content['tool_results']['content']:
                                            if tool_result['type'] == 'json':
                                                if tool_result['json'].get('searchResults') is not None:
                                                    doc_panels = []
                                                    for doc in tool_result['json'].get('searchResults'):
                                                        if self.enable_markdown:
                                                            doc_text = Markdown(doc['text'])
                                                        else:
                                                            doc_text = doc['text']
                                                        doc_panels.append(Panel(doc_text, title=f"[bold black]{doc['doc_title']} (Doc-ID: {doc['doc_id']}, Source-ID: {int(doc['source_id'])})", padding=self.panel_padding))
                                                    group = Group(*doc_panels)
                                                    #outer_panel = Panel(group, title=f"[bold black]Tool Results:{content['tool_results']['name']}", padding=self.outer_panel_padding)
                                                    outer_panel = Panel(group, title=f"[bold black]Tool Results:{self.last_tool_name}", padding=self.outer_panel_padding)
                                                    if self.console_print:
                                                        console.print(outer_panel)
                                                    else:
                                                        with console.capture() as capture:
                                                            console.print(outer_panel)
                                                        yield capture.get()

                                if content['tool_results']['name'] in self.analyst_service_names:
                                    if self.display_tool_results_sql:
                                        for tool_result in content['tool_results']['content']:
                                            if tool_result['type'] == 'json':
                                                if tool_result['json'].get('sql') is not None:
                                                    sql_interpretation = tool_result['json'].get('text').replace('This is our interpretation of your question:\n\n','')
                                                    sql_interpretation_panel = Panel(sql_interpretation, title="[bold black]Interpreation of Question", padding=self.panel_padding)
                                                    sql = Syntax(tool_result['json'].get('sql'), "sql", theme="monokai", line_numbers=True)
                                                    sql_panel = Panel(sql, title="[bold black]Generated SQL Query", padding=self.panel_padding)
                                                    group = Group(sql_interpretation_panel, sql_panel)
                                                    outer_panel = Panel(group, title=f"[bold black]Tool Results:{content['tool_results']['name']}", padding=self.outer_panel_padding)
                                                    if self.console_print:
                                                        console.print(outer_panel)
                                                    else:
                                                        with console.capture() as capture:
                                                            console.print(outer_panel)
                                                        yield capture.get()
                                
                                if content['tool_results']['name'] in self.data_to_chart_names:
                                    if self.display_tool_results_chart:
                                        for tool_result in content['tool_results']['content']:
                                            if tool_result['type'] == 'json':
                                                chart_text = f"Chart rendering not possible in Text-interface. The retrieved vega-lite chart:\n"
                                                json_syntax = Syntax(json.dumps(tool_result['json'], indent=2), "json", line_numbers=True, indent_guides=True)
                                                chart_panel = Panel(Group(chart_text, json_syntax), title="[bold black]Generated Chart", padding=self.panel_padding)
                                                outer_panel = Panel(chart_panel, title=f"[bold black]Tool Results: data_to_chart", padding=self.outer_panel_padding)
                                                if self.console_print:
                                                    console.print(outer_panel)
                                                else:
                                                    with console.capture() as capture:
                                                        console.print(outer_panel)
                                                    yield capture.get()
                        
                        if content['type'] == 'chart':
                            if self.display_charts:
                                chart_spec = json.loads(content['chart']['chart_spec'])
                                chart_text = f"Chart rendering not possible in Text-interface but I can summarize the chart based on the data and the vega chart spec:\n"
                                json_syntax = Syntax(json.dumps(chart_spec, indent=2), "json", line_numbers=True, indent_guides=True)
                                if self.summarize_charts:
                                    chart_summary = generate_chart_summary(self.agent, user_prompt=self.user_prompt, chart_spec=chart_spec)
                                    chart_summary = "".join(chart_summary)
                                chart_panel = Panel(Group(chart_text, chart_summary, json_syntax), title="[bold black]Generated Chart", padding=self.panel_padding)
                                outer_panel = Panel(chart_panel, title=f"[bold black]Chart Results: data_to_chart", padding=self.outer_panel_padding)
                                if self.console_print:
                                    console.print(outer_panel)
                                else:
                                    with console.capture() as capture:
                                        console.print(outer_panel)
                                    yield capture.get()

                        if content.get('type') == 'text':
                            if self.display_text_results:
                                self.text_output += content['text'].replace('【', '[').replace('】', ']')


class ConversationalCallback:
    """
    Callback for generating conversational (text-only) responses from the agent.

    This callback formats responses to mimic a conversation by prefixing user and 
    assistant messages with labels and by providing text-based summaries of tool results.

    Keyword Args:
        display_tool_use (bool): Whether to describe tool usage.
        display_tool_results (bool): Whether to include tool results in the output.
        display_charts (bool): Whether to output chart specs.
        display_text_results (bool): Whether to output text results.
        (Other display_* flags control display behavior for specific tool types.)
    """
    def __init__(self, agent, **kwargs):
        self.agent = agent

        # Turn on/off results
        self.display_tool_use = kwargs.get('display_tool_use', True)
        self.display_tool_use_sql = kwargs.get('display_tool_use_sql', True)
        self.display_tool_use_search = kwargs.get('display_tool_use_search', True)
        self.display_tool_use_sql_exec = kwargs.get('display_tool_use_sql_exec', True)
        self.display_tool_use_data_to_chart = kwargs.get('display_tool_use_data_to_chart', True)
        self.display_tool_results = kwargs.get('display_tool_results', True)
        self.display_tool_results_search_results = kwargs.get('display_tool_results_search_results', True)
        self.display_tool_results_sql = kwargs.get('display_tool_results_sql', True)
        self.display_tool_results_data = kwargs.get('display_tool_results_data', True)
        self.display_tool_results_chart = kwargs.get('display_tool_results_chart', False)
        self.display_charts = kwargs.get('display_charts', True)
        self.display_text_results = kwargs.get('display_text_results', True)
        self.summarize_charts = kwargs.get('summarize_charts', True)

        # fixed variables
        self.analyst_service_names = [tool.name for tool in agent.configuration.tools if tool.type == 'cortex_analyst_text_to_sql']
        self.search_service_names = [tool.name for tool in agent.configuration.tools if tool.type == 'cortex_search']
        self.sql_exec_names = [tool.name for tool in agent.configuration.tools if tool.type == 'sql_exec']
        self.data_to_chart_names = ['data_to_chart']

        self.text_output = ''
        self.last_tool_name = None # temporary bugfix, since tool_results.name is empty for Cortex Search
        self.first_text_response = True
        self.user_prompt = ''

    def __call__(self, message: Union[Message, ServerSentEvent]):
        if isinstance(message, Message):
            if message['role'] == 'user':
                if message['content'][0]['type'] == 'text':
                    text = [
                        f"User:",
                        f"{message['content'][0]['text']}",
                        '\n'
                    ]
                    yield "\n".join(text)
                    self.user_prompt = message['content'][0]['text']

                if message['content'][0]['type'] == 'tool_results':
                    if self.display_tool_results_data:
                        tool_name = message['content'][0]['tool_results']['name']
                        query_id = message['content'][0]['tool_results']['content'][0]['json']['query_id']
                        df = message['content'][0]['tool_results']['content'][0]['json']['query_df']
                        text = [
                            f"User:",
                            f"These are the results of the executed SQL Query with Query-ID: {query_id})",
                            f"{df.to_markdown()}",
                            '\n'
                        ]
                        yield "\n".join(text)

        if isinstance(message, ServerSentEvent):
            event = message
            if event.event == "done":
                self.text_output = ''
                self.first_text_response = True
            if event.event == "message.delta":
                data = json.loads(event.data)
                if "delta" in data and "content" in data["delta"]:
                    for content in data['delta']['content']:

                        if content['type'] == 'tool_use':
                            if self.display_tool_use:
                                if self.display_tool_use_sql:
                                    if content['tool_use']['name'] in self.analyst_service_names:
                                        text = [
                                            f"Assistant:",
                                            f"I will use {content['tool_use']['name']} to generate a SQL query for the answer.",
                                            '\n'
                                        ]
                                        yield "\n".join(text)
                                
                                    if content['tool_use']['name'] in self.search_service_names:
                                        if self.display_tool_use_search:
                                            text = [
                                                f"Assistant:",
                                                f"I will use {content['tool_use']['name']} with the following inputs to serve your request:",
                                            ]
                                            text.append(f"* Query: {content['tool_use']['input'].get('query')}")
                                            text.append(f"* Filters: {content['tool_use']['input'].get('filters')}")
                                            text.append(f"* Limit: {content['tool_use']['input'].get('limit')}")
                                            text.append(f"* Columns: {content['tool_use']['input'].get('columns')}")
                                            text.append('\n')
                                            yield "\n".join(text)
                                            # temporary bugfix
                                            self.last_tool_name = content['tool_use']['name']

                                if content['tool_use']['name'] in self.sql_exec_names:
                                    if self.display_tool_use_sql_exec:
                                        sql = content['tool_use']['input']['query']
                                        text = [
                                            f"Assistant:",
                                            f"I will use {content['tool_use']['name']} to execute the generated SQL query.",
                                            '\n'
                                        ]
                                        yield "\n".join(text)
                                
                                if content['tool_use']['name'] in  self.data_to_chart_names:
                                    if self.display_tool_use_data_to_chart:
                                        text = [
                                            f"Assistant:",
                                            f"I will use {content['tool_use']['name']} to generate an appropriate chart based on the data and your question.",
                                            '\n'
                                        ]
                                        yield "\n".join(text)

                        if content['type'] == 'tool_results':
                            if self.display_tool_results:
                                #if content['tool_results']['name'] in self.search_service_names:
                                if content['tool_results']['name'] in self.search_service_names or self.last_tool_name in self.search_service_names:
                                    if self.display_tool_results_search_results:
                                        for tool_result in content['tool_results']['content']:
                                            if tool_result['type'] == 'json':
                                                if tool_result['json'].get('searchResults') is not None:
                                                    number_of_docs = len(tool_result['json'].get('searchResults'))
                                                    text = [
                                                        f"Assistant:",
                                                        f"I found {number_of_docs} documents relevant for your question."
                                                    ]
                                                    for doc in tool_result['json'].get('searchResults'):
                                                        text.append(f"* {doc['doc_title']} (Doc-ID: {doc['doc_id']}, Source-ID: {int(doc['source_id'])})")
                                                    text.append('\n')
                                                    yield "\n".join(text)

                                if content['tool_results']['name'] in self.analyst_service_names:
                                    if self.display_tool_results_sql:
                                        for tool_result in content['tool_results']['content']:
                                            if tool_result['type'] == 'json':
                                                if tool_result['json'].get('sql') is not None:
                                                    sql_interpretation = tool_result['json'].get('text').replace('This is our interpretation of your question:\n\n','')
                                                    sql = tool_result['json'].get('sql')
                                                    text = [
                                                        f"Assistant:",
                                                        f"{content['tool_results']['name']} interpreted your question like this:",
                                                        f'"{sql_interpretation}"',
                                                        f"Based on this interpretation the following SQL was genereated:",
                                                        sql,
                                                        '\n'
                                                    ]
                                                    yield "\n".join(text)
                                
                                if content['tool_results']['name'] in self.data_to_chart_names:
                                    if self.display_tool_results_chart:
                                        for tool_result in content['tool_results']['content']:
                                            if tool_result['type'] == 'json':
                                                json_syntax = json.dumps(tool_result['json'], indent=2)
                                                text = [
                                                    f"Assistant:",
                                                    f"Chart rendering is not possible in Text-interface but I can summarize the chart based on the data and the vega chart spec:\n",
                                                    json_syntax,
                                                    '\n'
                                                ]
                                                yield "\n".join(text)
                        
                        if content['type'] == 'chart':
                            if self.display_charts:
                                chart_spec = json.loads(content['chart']['chart_spec'])
                                json_syntax = json.dumps(chart_spec, indent=2)

                                text = [
                                    f"Assistant:",
                                    f"Chart rendering is not possible in Text-interface but I can summarize the chart based on the data and the vega chart spec:\n",
                                    json_syntax,
                                    '\n'
                                ]
                                yield "\n".join(text)
                                if self.summarize_charts:
                                    chart_summary = generate_chart_summary(self.agent, user_prompt=self.user_prompt, chart_spec=chart_spec)
                                    for chunk in chart_summary:
                                        yield chunk

                        if content.get('type') == 'text':
                            if self.first_text_response:
                                yield 'Assistant:\n'
                                self.first_text_response = False
                            if self.display_text_results:
                                yield content['text']

class MinimalisticCallback:
    """
    Minimalistic callback that returns simple text outputs from the agent.

    This callback is designed to produce a concise conversation format, displaying
    only the essential user and assistant messages.

    Attributes:
        first_text_response (bool): Tracks if the first text response has been sent.
    """
    def __init__(self):
        self.first_text_response = True

    def __call__(self, message: Union[Message, ServerSentEvent]):
        if isinstance(message, Message):
            response_string = f"User Message:\n{message['content'][0]['text']}\n\n"
            yield response_string
        if isinstance(message, ServerSentEvent):
            if message.event == "done":
                self.first_text_response = True
            if message.event == 'message.delta':
                data = json.loads(message.data)
                if data['delta']['content'][0]['type'] == 'text':
                    if self.first_text_response:
                        yield 'Assistant Message:\n'
                        self.first_text_response = False
                    yield data['delta']['content'][0]['text']


class StreamlitCallback:
    def __init__(self, agent, **kwargs):
        self.agent = agent

        # Turn on/off results
        self.display_tool_use = kwargs.get('display_tool_use', True)
        self.display_tool_use_sql = kwargs.get('display_tool_use_sql', True)
        self.display_tool_use_search = kwargs.get('display_tool_use_search', True)
        self.display_tool_use_sql_exec = kwargs.get('display_tool_use_sql_exec', True)
        self.display_tool_use_data_to_chart = kwargs.get('display_tool_use_data_to_chart', True)
        self.display_tool_results = kwargs.get('display_tool_results', True)
        self.display_tool_results_search_results = kwargs.get('display_tool_results_search_results', True)
        self.display_tool_results_sql = kwargs.get('display_tool_results_sql', True)
        self.display_tool_results_data = kwargs.get('display_tool_results_data', True)
        self.display_tool_results_chart = kwargs.get('display_tool_results_chart', False)
        self.display_charts = kwargs.get('display_charts', True)
        self.display_text_results = kwargs.get('display_text_results', True)
        self.streamed_responses = kwargs.get('streamed_responses', True)
        self.summarize_charts = kwargs.get('summarize_charts', True)

        self.enable_markdown = kwargs.get('enable_markdown', True)

        # fixed variables
        self.analyst_service_names = [tool.name for tool in agent.configuration.tools if tool.type == 'cortex_analyst_text_to_sql']
        self.search_service_names = [tool.name for tool in agent.configuration.tools if tool.type == 'cortex_search']
        self.sql_exec_names = [tool.name for tool in agent.configuration.tools if tool.type == 'sql_exec']
        self.data_to_chart_names = ['data_to_chart'] # always data_to_chart #[tool.name for tool in agent.configuration.tools if tool.type == 'data_to_chart']
        self.text_response = ''
        self.last_tool_name = None # temporary bugfix, since tool_results.name is empty for Cortex Search
        self.first_text_response = True
        self.user_prompt = ''

    def response_streamer(self, text_response):
        for char in text_response:
            yield char
            time.sleep(0.007)

    def __call__(self, message: Union[Message, ServerSentEvent]):
        if isinstance(message, Message):
            if message['role'] == 'user':
                if message['content'][0]['type'] == 'text':
                    text = message['content'][0]['text']
                    chat_message = st.chat_message('user')
                    chat_message.write(text)
                    self.user_prompt = text

            if message['content'][0]['type'] == 'tool_results':
                if self.display_tool_results_data:
                    tool_name = message['content'][0]['tool_results']['name']
                    query_id = message['content'][0]['tool_results']['content'][0]['json']['query_id']
                    df = message['content'][0]['tool_results']['content'][0]['json']['query_df']
                    chat_message = st.chat_message('user')
                    if self.streamed_responses:
                        chat_message.write_stream(self.response_streamer(f"These are the results of the executed SQL Query with Query-ID: {query_id})"))
                    else:
                        chat_message.write(f"These are the results of the executed SQL Query with Query-ID: {query_id})")
                    chat_message.dataframe(df)
        if isinstance(message, ServerSentEvent):
            event = message
            if event.event == "done":
                if self.display_text_results:
                    if self.text_response != '':
                        chat_message = st.chat_message('ai')
                        if self.streamed_responses:
                            chat_message.write_stream(self.response_streamer(self.text_response))
                        else:
                            chat_message.write(self.text_response)
                self.text_response = ''
                self.first_text_response = True

            if event.event == "message.delta":
                data = json.loads(event.data)
                if "delta" in data and "content" in data["delta"]:
                    for content in data['delta']['content']:
                        if content['type'] == 'tool_use':
                            if self.display_tool_use:
                                if self.display_tool_use_sql:
                                    if content['tool_use']['name'] in self.analyst_service_names:
                                        chat_message = st.chat_message('ai')
                                        if self.streamed_responses:
                                            chat_message.write_stream(self.response_streamer(f"I will use {content['tool_use']['name']} to generate a SQL query for the answer."))
                                        else:
                                            chat_message.write(f"I will use {content['tool_use']['name']} to generate a SQL query for the answer.")

                                    if content['tool_use']['name'] in self.search_service_names:
                                        if self.display_tool_use_search:
                                            chat_message = st.chat_message('ai')
                                            text = [
                                                f"I will use {content['tool_use']['name']} with the following inputs to serve your request:",
                                            ]
                                            text.append(f"* Query: {content['tool_use']['input'].get('query')}")
                                            text.append(f"* Filters: {content['tool_use']['input'].get('filters')}")
                                            text.append(f"* Limit: {content['tool_use']['input'].get('limit')}")
                                            text.append(f"* Columns: {content['tool_use']['input'].get('columns')}")
                                            if self.streamed_responses:
                                                chat_message.write_stream(self.response_streamer("\n".join(text)))
                                            else:
                                                chat_message.write("\n".join(text))
                                            # temporary bugfix
                                            self.last_tool_name = content['tool_use']['name']
                                
                                    if content['tool_use']['name'] in self.sql_exec_names:
                                        if self.display_tool_use_sql_exec:
                                            chat_message = st.chat_message('ai')
                                            sql = content['tool_use']['input']['query']
                                            if self.streamed_responses:
                                                chat_message.write_stream(self.response_streamer(f"I will use {content['tool_use']['name']} to execute the generated SQL query."))
                                            else:
                                                chat_message.write(f"I will use {content['tool_use']['name']} to execute the generated SQL query.")
                                    
                                    if content['tool_use']['name'] in  self.data_to_chart_names:
                                        if self.display_tool_use_data_to_chart:
                                            chat_message = st.chat_message('ai')
                                            if self.streamed_responses:
                                                chat_message.write_stream(self.response_streamer(f"I will use {content['tool_use']['name']} to generate an appropriate chart based on the data and your question."))
                                            else:
                                                chat_message.write(f"I will use {content['tool_use']['name']} to generate an appropriate chart based on the data and your question.")


                        if content['type'] == 'tool_results':
                            if self.display_tool_results:
                                #if content['tool_results']['name'] in self.search_service_names:
                                if content['tool_results']['name'] in self.search_service_names or self.last_tool_name in self.search_service_names:
                                    if self.display_tool_results_search_results:
                                        for tool_result in content['tool_results']['content']:
                                            if tool_result['type'] == 'json':
                                                if tool_result['json'].get('searchResults') is not None:
                                                    chat_message = st.chat_message('ai')
                                                    number_of_docs = len(tool_result['json'].get('searchResults'))
                                                    if self.streamed_responses:
                                                        chat_message.write_stream(self.response_streamer(f"I found {number_of_docs} documents relevant for your question."))
                                                    else:
                                                        chat_message.write(f"I found {number_of_docs} documents relevant for your question.")
                                                    for doc in tool_result['json'].get('searchResults'):
                                                        with chat_message.expander(f"**{doc['doc_title']} (Doc-ID: {doc['doc_id']}, Source-ID: {int(doc['source_id'])})**", expanded=False):
                                                            if self.enable_markdown:
                                                                st.markdown(doc['text'])
                                                            else:
                                                                st.write(doc['text'])

                                if content['tool_results']['name'] in self.analyst_service_names:
                                    if self.display_tool_results_sql:
                                        for tool_result in content['tool_results']['content']:
                                            if tool_result['type'] == 'json':
                                                if tool_result['json'].get('sql') is not None:
                                                    chat_message = st.chat_message('ai')
                                                    sql_interpretation = tool_result['json'].get('text').replace('This is our interpretation of your question:\n\n','')
                                                    sql = tool_result['json'].get('sql')
                                                    if self.streamed_responses:
                                                        chat_message.write_stream(self.response_streamer(f"{content['tool_results']['name']} interpreted your question like this:"))
                                                        chat_message.write_stream(self.response_streamer(f"_{sql_interpretation}_"))
                                                        chat_message.write_stream(self.response_streamer(f"Based on this interpretation the following SQL was genereated:"))
                                                    else:
                                                        chat_message.write(f"{content['tool_results']['name']} interpreted your question like this:")
                                                        chat_message.write(f"_{sql_interpretation}_")
                                                        chat_message.write(f"Based on this interpretation the following SQL was genereated:")
                                                    chat_message.code(sql, language='sql', line_numbers=True)

                                if content['tool_results']['name'] in self.data_to_chart_names:
                                    if self.display_tool_results_chart:
                                        for tool_result in content['tool_results']['content']:
                                            if tool_result['type'] == 'json':
                                                chat_message = st.chat_message('ai')
                                                chart_text = f"Chart rendering not possible in Text-interface but this is the generated vega-lite chart:"
                                                chart_spec = tool_result['json']
                                                chart_spec_json = json.dumps(chart_spec, indent=2)
                                                if self.streamed_responses:
                                                    chat_message.write_stream(self.response_streamer(f"Chart rendering is not possible in Text-interface but this is the generated vega-lite chart spec:"))
                                                else:
                                                    chat_message.write_stream(f"Chart rendering is not possible in Text-interface but this is the generated vega-lite chart spec:")
                                                chat_message.vega_lite_chart(spec=chart_spec, height=500, width=1000)
                                                chat_message.expander('Vega-Lite-Spec', expanded=False).code(chart_spec_json, language='json', line_numbers=True)

                        if content['type'] == 'chart':
                            if self.display_charts:
                                chat_message = st.chat_message('ai')
                                chart_spec = json.loads(content['chart']['chart_spec'])
                                chart_spec_json = json.dumps(chart_spec, indent=2)
                                if self.streamed_responses:
                                    chat_message.write_stream(self.response_streamer(f"Here is the generated chart for your question:"))
                                else:
                                    chat_message.write(f"Here is the generated chart for your question:")
                                chat_message.vega_lite_chart(spec=chart_spec, height=500, width=1000)
                                if self.summarize_charts:
                                    chart_summary = generate_chart_summary(self.agent, user_prompt=self.user_prompt, chart_spec=chart_spec)
                                    chat_message.write_stream(chart_summary)
                                chat_message.expander('Vega-Lite-Spec', expanded=False).code(chart_spec_json, language='json', line_numbers=True)
                                
                        
                        if content.get('type') == 'text':
                            self.text_response += content["text"]


class StreamlitMessageHandler:
    def __init__(self, agent, **kwargs):
        self.agent = agent

        # Turn on/off results
        self.display_tool_use = kwargs.get('display_tool_use', True)
        self.display_tool_use_sql = kwargs.get('display_tool_use_sql', True)
        self.display_tool_use_search = kwargs.get('display_tool_use_search', True)
        self.display_tool_use_sql_exec = kwargs.get('display_tool_use_sql_exec', True)
        self.display_tool_use_data_to_chart = kwargs.get('display_tool_use_data_to_chart', True)
        self.display_tool_results = kwargs.get('display_tool_results', True)
        self.display_tool_results_search_results = kwargs.get('display_tool_results_search_results', True)
        self.display_tool_results_sql = kwargs.get('display_tool_results_sql', True)
        self.display_tool_results_data = kwargs.get('display_tool_results_data', True)
        self.display_tool_results_chart = kwargs.get('display_tool_results_chart', False)
        self.display_charts = kwargs.get('display_charts', True)
        self.display_text_results = kwargs.get('display_text_results', True)
        self.streamed_responses = kwargs.get('streamed_responses', False)
        self.summarize_charts = kwargs.get('summarize_charts', True)

        self.enable_markdown = kwargs.get('enable_markdown', True)

        # fixed variables
        self.analyst_service_names = [tool.name for tool in agent.configuration.tools if tool.type == 'cortex_analyst_text_to_sql']
        self.search_service_names = [tool.name for tool in agent.configuration.tools if tool.type == 'cortex_search']
        self.sql_exec_names = [tool.name for tool in agent.configuration.tools if tool.type == 'sql_exec']
        self.data_to_chart_names = ['data_to_chart'] # always data_to_chart #[tool.name for tool in agent.configuration.tools if tool.type == 'data_to_chart']
        self.text_response = ''
        self.last_tool_name = None # temporary bugfix, since tool_results.name is empty for Cortex Search
        self.first_text_response = True
        self.user_prompt = ''


    def __call__(self, message: dict):
        if message['role'] == 'user':
            if message['content'][0]['type'] == 'text':
                text = message['content'][0]['text']
                chat_message = st.chat_message('user')
                chat_message.write(text)
                self.user_prompt = text

            if message['content'][0]['type'] == 'tool_results':
                if self.display_tool_results_data:
                    tool_name = message['content'][0]['tool_results']['name']
                    query_id = message['content'][0]['tool_results']['content'][0]['json']['query_id']
                    df = message['content'][0]['tool_results']['content'][0]['json']['query_df']
                    chat_message = st.chat_message('user')
                    if self.streamed_responses:
                        chat_message.write_stream(self.response_streamer(f"These are the results of the executed SQL Query with Query-ID: {query_id})"))
                    else:
                        chat_message.write(f"These are the results of the executed SQL Query with Query-ID: {query_id})")
                    chat_message.dataframe(df)

        if message['role'] == 'assistant':
            for content in message['content']:
                if content['type'] == 'tool_use':
                    if self.display_tool_use:
                        if self.display_tool_use_sql:
                            if content['tool_use']['name'] in self.analyst_service_names:
                                chat_message = st.chat_message('ai')
                                if self.streamed_responses:
                                    chat_message.write_stream(self.response_streamer(f"I will use {content['tool_use']['name']} to generate a SQL query for the answer."))
                                else:
                                    chat_message.write(f"I will use {content['tool_use']['name']} to generate a SQL query for the answer.")

                            if content['tool_use']['name'] in self.search_service_names:
                                if self.display_tool_use_search:
                                    chat_message = st.chat_message('ai')
                                    text = [
                                        f"I will use {content['tool_use']['name']} with the following inputs to serve your request:",
                                    ]
                                    text.append(f"* Query: {content['tool_use']['input'].get('query')}")
                                    text.append(f"* Filters: {content['tool_use']['input'].get('filters')}")
                                    text.append(f"* Limit: {content['tool_use']['input'].get('limit')}")
                                    text.append(f"* Columns: {content['tool_use']['input'].get('columns')}")
                                    if self.streamed_responses:
                                        chat_message.write_stream(self.response_streamer("\n".join(text)))
                                    else:
                                        chat_message.write("\n".join(text))
                                    # temporary bugfix
                                    self.last_tool_name = content['tool_use']['name']
                        
                            if content['tool_use']['name'] in self.sql_exec_names:
                                if self.display_tool_use_sql_exec:
                                    chat_message = st.chat_message('ai')
                                    sql = content['tool_use']['input']['query']
                                    if self.streamed_responses:
                                        chat_message.write_stream(self.response_streamer(f"I will use {content['tool_use']['name']} to execute the generated SQL query."))
                                    else:
                                        chat_message.write(f"I will use {content['tool_use']['name']} to execute the generated SQL query.")
                            
                            if content['tool_use']['name'] in  self.data_to_chart_names:
                                if self.display_tool_use_data_to_chart:
                                    chat_message = st.chat_message('ai')
                                    if self.streamed_responses:
                                        chat_message.write_stream(self.response_streamer(f"I will use {content['tool_use']['name']} to generate an appropriate chart based on the data and your question."))
                                    else:
                                        chat_message.write(f"I will use {content['tool_use']['name']} to execute the generated SQL query.")


                if content['type'] == 'tool_results':
                    if self.display_tool_results:
                        #if content['tool_results']['name'] in self.search_service_names:
                        if content['tool_results']['name'] in self.search_service_names or self.last_tool_name in self.search_service_names:
                            if self.display_tool_results_search_results:
                                for tool_result in content['tool_results']['content']:
                                    if tool_result['type'] == 'json':
                                        if tool_result['json'].get('searchResults') is not None:
                                            chat_message = st.chat_message('ai')
                                            number_of_docs = len(tool_result['json'].get('searchResults'))
                                            if self.streamed_responses:
                                                chat_message.write_stream(self.response_streamer(f"I found {number_of_docs} documents relevant for your question."))
                                            else:
                                                chat_message.write(f"I found {number_of_docs} documents relevant for your question.")
                                            for doc in tool_result['json'].get('searchResults'):
                                                with chat_message.expander(f"**{doc['doc_title']} (Doc-ID: {doc['doc_id']}, Source-ID: {int(doc['source_id'])})**", expanded=False):
                                                    if self.enable_markdown:
                                                        st.markdown(doc['text'])
                                                    else:
                                                        st.write(doc['text'])

                        if content['tool_results']['name'] in self.analyst_service_names:
                            if self.display_tool_results_sql:
                                for tool_result in content['tool_results']['content']:
                                    if tool_result['type'] == 'json':
                                        if tool_result['json'].get('sql') is not None:
                                            chat_message = st.chat_message('ai')
                                            sql_interpretation = tool_result['json'].get('text').replace('This is our interpretation of your question:\n\n','')
                                            sql = tool_result['json'].get('sql')
                                            if self.streamed_responses:
                                                chat_message.write_stream(self.response_streamer(f"{content['tool_results']['name']} interpreted your question like this:"))
                                                chat_message.write_stream(self.response_streamer(f"_{sql_interpretation}_"))
                                                chat_message.write_stream(self.response_streamer(f"Based on this interpretation the following SQL was genereated:"))
                                            else:
                                                chat_message.write(f"{content['tool_results']['name']} interpreted your question like this:")
                                                chat_message.write(f"_{sql_interpretation}_")
                                                chat_message.write(f"Based on this interpretation the following SQL was genereated:")
                                            chat_message.code(sql, language='sql', line_numbers=True)

                        if content['tool_results']['name'] in self.data_to_chart_names:
                            if self.display_tool_results_chart:
                                for tool_result in content['tool_results']['content']:
                                    if tool_result['type'] == 'json':
                                        chat_message = st.chat_message('ai')
                                        chart_text = f"Chart rendering not possible in Text-interface but this is the generated vega-lite chart:"
                                        chart_spec = tool_result['json']
                                        chart_spec_json = json.dumps(chart_spec, indent=2)
                                        if self.streamed_responses:
                                            chat_message.write_stream(self.response_streamer(f"Chart rendering is not possible in Text-interface but this is the generated vega-lite chart spec:"))
                                        else:
                                            chat_message.write_stream(f"Chart rendering is not possible in Text-interface but this is the generated vega-lite chart spec:")
                                        chat_message.vega_lite_chart(spec=chart_spec, height=500, width=1000)
                                        chat_message.expander('Vega-Lite-Spec', expanded=False).code(chart_spec_json, language='json', line_numbers=True)

                if content['type'] == 'chart':
                    if self.display_charts:
                        chat_message = st.chat_message('ai')
                        chart_spec = json.loads(content['chart']['chart_spec'])
                        chart_spec_json = json.dumps(chart_spec, indent=2)
                        if self.streamed_responses:
                            chat_message.write_stream(self.response_streamer(f"Here is the generated chart for your question:"))
                        else:
                            chat_message.write(f"Here is the generated chart for your question:")
                        chat_message.vega_lite_chart(spec=chart_spec, height=500, width=1000)
                        if self.summarize_charts:
                            chart_summary = generate_chart_summary(self.agent, user_prompt=self.user_prompt, chart_spec=chart_spec)
                            chat_message.write_stream(chart_summary)
                        chat_message.expander('Vega-Lite-Spec', expanded=False).code(chart_spec_json, language='json', line_numbers=True)
                        
                
                if content.get('type') == 'text':
                    with st.chat_message('assistant'):
                        st.write(content["text"])