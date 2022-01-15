"""
    http_handler.py: handle the lifecycle http protocol
"""

import socket
from typing import Optional
from collections import deque
import threading
import logging

from .connection import TcpConnection
from .http_parser import HttpParser
from .constants import CONNECTION_ESTABLISHED_MESSAGE
from .flag import flags
from .cert import CertificateHelper


logger = logging.getLogger(__name__)


class HttpProxyHandler:

    def __init__(self, client: TcpConnection, work_queue: deque,
                 lock: threading.Lock):
        self.client = client
        self.work_queue = work_queue
        self.lock = lock
        self.upstream: Optional[TcpConnection] = None
        self.request = HttpParser()
        self.id = self.client.get_id()
        self.client.set_handler_id(self.id)
        self.wrap_client_after_flush = False

    def connect_upstream(self):
        assert self.request.host and self.request.port
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((self.request.host, self.request.port))
        sock.setblocking(False)
        logger.info('Connect to upstream %s:%d, fd %d',
                    self.request.host, self.request.port, sock.fileno())
        self.upstream = TcpConnection(sock, self.request.host, 'upstream')
        self.upstream.set_handler_id(self.id)
        if self.request.has_buffer():
            self.pipe_data_to_upstream(self.request.get_buffer())
        self.pipe_data_to_client(CONNECTION_ESTABLISHED_MESSAGE)
        with self.lock:
            self.work_queue.append(self.upstream)
        if flags.args.man_in_the_middle and self.request.port == 443:
            if self.client.has_buffer():
                self.wrap_client_after_flush = True
            else:
                self.client.wrap_socket(self.request.host)
            self.upstream.wrap_socket(self.request.host)

    def read_from_fd(self, fd):
        if fd == self.client.fileno():
            return self.recv_from_client()
        elif self.upstream and fd == self.upstream.fileno():
            return self.recv_from_upstream()

    def write_to_fd(self, fd):
        if fd == self.client.fileno():
            return self.send_to_client()
        elif self.upstream and fd == self.upstream.fileno():
            return self.send_to_upstream()

    def recv_from_client(self):
        data = self.client.recv()
        if data is None:
            self.close_client()
            # also close the upstream
            self.close_upstream()
            return True
        if self.request.is_completed():
            assert self.upstream
            self.pipe_data_to_upstream(data)
        else:
            self.request.parse(data)
            if not self.upstream and self.request.has_host():
                self.connect_upstream()
        return False

    def recv_from_upstream(self):
        assert self.upstream
        data = self.upstream.recv()
        if data is None:
            self.close_upstream()
            # also close the client
            self.close_client()
            return True
        self.pipe_data_to_client(data)
        return False

    def send_to_client(self):
        n = self.client.flush()
        if self.wrap_client_after_flush:
            if not self.client.has_buffer():
                self.client.wrap_socket(self.request.host)
                self.wrap_client_after_flush = False
        return n

    def send_to_upstream(self):
        assert self.upstream
        return self.upstream.flush()

    def pipe_data_to_client(self, data):
        self.client.push_buffer(data)

    def pipe_data_to_upstream(self, data):
        assert self.upstream
        self.upstream.push_buffer(data)

    def close_client(self):
        self.client.flush_close()

    def close_upstream(self):
        if self.upstream:
            self.upstream.flush_close()
