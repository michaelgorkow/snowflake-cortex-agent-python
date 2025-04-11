from snowflake.snowpark.context import get_active_session
from dataclasses import dataclass, field
from typing import Optional
from snowflake.snowpark import Session
import logging
from .jwt_generator import JWTGenerator
from datetime import timedelta
from snowflake.snowpark.exceptions import SnowparkSessionException
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
import logging
from .environment_checks import is_running_in_snowflake_notebook

logger = logging.getLogger("cortex_agent.connection")

API_ENDPOINT = "/api/v2/cortex/agent:run"
API_TIMEOUT = 50000
JWT_LIFE_TIME = 59
JWT_RENEWAL = 54
CORTEX_API_ENDPOINT = '/api/v2/cortex/inference:complete'

@dataclass
class CortexAgentConnection:
    """
    Manages the authentication and connection details for the Cortex Agent.

    This class supports multiple authentication methods:
    - Using an existing Snowflake session.
    - Using a private key file with connection parameters.
    - Using a programmatic access token with connection parameters.

    It handles token generation (JWT and Snowflake tokens), session creation, and 
    formatting of the account URL for API calls.

    Attributes:
        session (Optional[Session]): A Snowflake session instance.
        private_key_file (Optional[str]): Path to the private key file for JWT generation.
        user (Optional[str]): The username for authentication.
        account_url (Optional[str]): Formatted account URL for API calls.
        connection_parameters (Optional[str]): Parameters required to establish a session.
        programmatic_access_token (Optional[str]): Access token for programmatic authentication.
        token (Optional[str]): Placeholder for a generated token.
        snowflake_token (Optional[str]): Token obtained from a Snowflake session.
        jwt_token (Optional[str]): JWT token generated for authentication.
    """
    session: Optional[Session] = None
    private_key_file: Optional[str] = None
    user: Optional[str] = None
    account_url: Optional[str] = None
    connection_parameters: Optional[str] = None
    programmatic_access_token: Optional[str] = None
    token: Optional[str] = None
    snowflake_token: Optional[str] = None
    jwt_token: Optional[str] = None

    def __post_init__(self):
        self.CORTEX_API_ENDPOINT = CORTEX_API_ENDPOINT
        self.API_ENDPOINT = API_ENDPOINT
        self.API_TIMEOUT = API_TIMEOUT
        has_session = self.session is not None
        has_key_file = self.private_key_file is not None
        has_pat = self.programmatic_access_token is not None
        has_connection_parameters = self.connection_parameters is not None

        # works from external
        # SQL: provided session
        # REST: builds token from session
        if has_session and not has_key_file and not has_pat and not has_connection_parameters:
            self._init_from_session()

        # works from external
        # SQL: build session with private key
        # REST: generated from private key
        elif has_key_file and has_connection_parameters and not has_session and not has_pat:
            self._init_from_private_key(create_session=True)

        # works from external + internal
        # SQL: provided session
        # REST: generated from private key
        elif has_key_file and has_connection_parameters and has_session and not has_pat:
            self._init_from_private_key(create_session=False)

        # works from external
        # SQL: build with PAT
        # REST: PAT
        elif has_pat and has_connection_parameters and not has_session and not has_key_file:
            self._init_from_programmatic_access_token(create_session=True)

        # works from external + internal
        # SQL: provided session
        # REST: PAT
        elif has_pat and not has_connection_parameters and has_session and not has_key_file:
            self._init_from_programmatic_access_token(create_session=False)

        else:
            logger.error(
                "❌ Invalid Authentication information.\n"
                "Provide either:\n"
                "1. Snowpark Session (for connection outside of Snowflake)\n"
                "2. Path to a file containing your private key, connection_parameters and session (optional).\n"
                "3. Programmatic Access Token, connection_parameters and session (optional).\n"
            )
            raise ValueError("Invalid Authentication information. See log for details.")



    def _init_from_session(self):
        """
        Use a provided session to run SQL statements and collect a token.
        Does not work inside of Snowflake since the session object can not issue tokens.
        """
        logger.info('Using provided session.')
        try:
            self.snowflake_token = self._get_token_from_session()
        except Exception as e:
            logger.error(f"Error: {e}")
        self.account_url = self._get_account_url_from_session()

    def _init_from_private_key(self, create_session=True):
        logger.info('Using provided key.')
        user = {k.lower(): v for k, v in self.connection_parameters.items()}.get('user')
        logger.info(f"Authenticating as user: {user}")
        if create_session == True:
            logger.info(f"Creating new session.")
            self.session = self._create_session_from_key(private_key_file=self.private_key_file, connection_parameters=self.connection_parameters)
        self.account_url = self._get_account_url_from_session()
        self.jwt_token = self._generate_jwt_token(self.account_url, user=user, private_key_file=self.private_key_file)

    def _init_from_programmatic_access_token(self, create_session=True):
        """
        Use a provided session to run SQL statements and collect a token.
        Does not work inside of Snowflake since the session object can not issue tokens.
        """
        logger.info('Using provided programmatic access token.')
        if create_session == True:
            self.session = self._create_session_from_programmatic_access_token(programmatic_access_token=self.programmatic_access_token, connection_parameters=self.connection_parameters)
        self.account_url = self._get_account_url_from_session()


    def _get_token_from_session(self):
        """
        Get a token from a Snowpark session for the Agent REST API.
        Does not work with sessions that are created as part of Snowflake Notebooks, Streamlit, etc. since the session object can not issue tokens.
        """
        self.session.sql(f"alter session set python_connector_query_result_format = json;").collect()
        token = self.session.connection._rest._token_request('ISSUE')['data']['sessionToken']
        self.session.sql(f"alter session set python_connector_query_result_format = arrow;").collect()
        logger.info(f"Successfully generated token: {token[0:30]}...")
        return token
    
    def _generate_jwt_token(self, account_url, user, private_key_file):
        """
        Generate a JWT token that is being used to authenticate.
        """
        token = JWTGenerator(account_url, user, private_key_file, timedelta(minutes=JWT_LIFE_TIME), timedelta(minutes=JWT_RENEWAL)).get_token()
        logger.info(f"Successfully generated token: {token[0:30]}...")
        return token
    
    def _get_account_url_from_session(self):
        """
        Retrieve and format account url from a Snowpark session.
        """
        if is_running_in_snowflake_notebook():
            org_name = self.session.sql('SELECT CURRENT_ORGANIZATION_NAME()').collect()[0][0]
            acc_name = self.session.sql('SELECT CURRENT_ACCOUNT_NAME()').collect()[0][0]
            acc_name = acc_name.replace('_','-')
            return f"{org_name}-{acc_name}.snowflakecomputing.com"
            #return f"""{self.session.sql("SELECT CONCAT(CURRENT_ORGANIZATION_NAME(),'-',REPLACE(CURRENT_ACCOUNT_NAME(), '_','-'))").collect()[0][0]}.snowflakecomputing.com"""
        else:
            return f"{self.session.get_current_account().replace('_','-')[1:-1]}.snowflakecomputing.com"
    
    def _create_session_from_key(self, private_key_file, connection_parameters):
        """
        Create a session given a private key file and connection parameters
        """
        # Load private key
        with open(private_key_file, "rb") as key_file:
            private_key = serialization.load_pem_private_key(
                key_file.read(),
                password=None,  # Use your passphrase here if your key is encrypted
                backend=default_backend()
            )

        # Convert to DER format for Snowflake
        pkb = private_key.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        connection_parameters['private_key'] = pkb
        return Session.builder.configs(connection_parameters).create()
    
    def _create_session_from_programmatic_access_token(self, programmatic_access_token, connection_parameters):
        """
        Create a session given a personal access token and connection parameters
        """
        connection_parameters['password'] = programmatic_access_token
        return Session.builder.configs(connection_parameters).create()
    
    def __repr__(self):
        # Create a dictionary of attributes, excluding the token
        attributes = {k: v for k, v in self.__dict__.items() if k not in ["jwt_token","snowflake_token","programmatic_access_token","connection_parameters"]}
        # include a placeholder for tokens if it's set
        attributes["jwt_token"] = "[OBFUSCATED]" if self.jwt_token is not None else None
        attributes["snowflake_token"] = "[OBFUSCATED]" if self.snowflake_token is not None else None
        attributes["programmatic_access_token"] = "[OBFUSCATED]" if self.programmatic_access_token is not None else None
        attributes["connection_parameters"] = "[OBFUSCATED]" if self.connection_parameters is not None else None
        return f"{self.__class__.__name__}({attributes})"