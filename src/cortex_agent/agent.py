class CortexAgent:
    """Handles all API calls to Cortex."""
    def __init__(self, account_url:str, model:str = 'claude-3-5-sonnet', response_instruction:str = '', tool_choice:str = 'auto'):
        self.account_url = account_url
        self.model = model
        self.response_instruction = response_instruction
        self.experimental = {}
        self.tools = []
        self.tool_resources = {}
        self.tool_choice = {'type':tool_choice}
        self.messages = []
        self.API_ENDPOINT = "/api/v2/cortex/agent:run"
        self.API_TIMEOUT = 50000  # in milliseconds

    def set_response_instruction(self, response_instruction:str = ''):
         self.response_instruction = response_instruction

    def add_tool(self, type, name):
        tool = {
            'tool_spec':{
                'type':type,
                'name':name
            }
        }
        self.tools.append(tool)

    def remove_tool(self):
        pass

    def add_tool_ressource(self, type:str, name:str, ressource_config:dict):
        if type == 'cortex_analyst_text_to_sql':
            self.tool_resources[name] = ressource_config
        if type == 'cortex_search':
            self.tool_resources[name] = ressource_config

    def remove_tool_ressource(self):
        pass

    def get_request(self):
        body = dict()
        body['model'] = self.model
        body['response_instruction'] = self.response_instruction
        body['experimental'] = self.experimental
        body['tools'] = self.tools
        body['tool_resources'] = self.tool_resources
        body['tool_choice'] = self.tool_choice
        body['messages'] = self.messages
        return body