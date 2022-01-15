"""
    http_parser.py: parse http request and response
"""

from .constants import CRLF, CONNECT_METHOD, GET_METHOD


class HttpParser:

    def __init__(self):
        self.host = None
        self.port = None
        self._buffer = b''
        self.completed = False

    def parse(self, data: bytes):
        self._buffer += data
        if self._buffer.endswith(CRLF * 2):
            if self._buffer.startswith(CONNECT_METHOD.encode()):
                a, self._buffer = self._buffer.split(CRLF * 2, 1)
                t1, t2, t3 = a.split(b' ', 2)
                host, port = t2.split(b':')
                self.host, self.port = host.decode(), int(port)
                self.completed = True
            elif self._buffer.startswith(GET_METHOD.encode()):
                ts = self._buffer.split(CRLF)
                _, path, _ = ts[0].split(b' ')
                self.port = 80
                if path.startswith(b'https://'):
                    self.port = 443
                    self.host = path.split(b'/')[2].decode()
                elif path.startswith(b'http://'):
                    self.host = path.split(b'/')[2].decode()
                if self.host is None:
                    for line in ts[1:]:
                        h, v = line.split(b':')
                        if h.lower() == b'host':
                            self.host = v.decode()
                            break
                self.completed = True

    def has_host(self):
        return self.host is not None and self.port is not None

    def is_completed(self):
        return self.completed

    def has_buffer(self):
        return len(self._buffer) > 0

    def get_buffer(self):
        return self._buffer
