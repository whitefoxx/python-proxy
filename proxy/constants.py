"""
    constants.py: define some useful constants.
"""

import selectors

EVENT_READ = selectors.EVENT_READ
EVENT_WRITE = selectors.EVENT_WRITE
BUFFER_SIZE = 4096
DEFAULT_SELECTOR_SELECT_TIMEOUT = 25 / 1000
CRLF = b'\r\n'
CONNECT_METHOD = 'CONNECT'
GET_METHOD = 'GET'

CONNECTION_ESTABLISHED_MESSAGE = b'HTTP/1.1 200 Connection Established\r\n\r\n'

DEFAULT_LOG_FILE = "proxy.log"
DEFAULT_LOG_FORMAT = '%(asctime)s - pid:%(process)d [%(levelname)-.1s] %(module)s.%(funcName)s:%(lineno)d - %(message)s'
DEFAULT_LOG_LEVEL = 'INFO'

