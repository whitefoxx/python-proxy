"""
    connection.py: TCP connection class
"""
from typing import Union
import socket
import ssl
import logging

from .constants import BUFFER_SIZE
from .cert import CertificateHelper

logger = logging.getLogger(__name__)


class TcpConnection:

    def __init__(self, sock, addr, tag='client'):
        self.sock: Union[socket.socket, ssl.SSLSocket] = sock
        self.addr = addr
        self.read_closed = False
        self.closed = False
        self.buffer: bytes = b''
        self.tag = tag
        self.handler_id = None
        self.selected_event = 0
        self.ssl_enable = False
        self.old_selected_sock = None

    def get_id(self):
        return self.sock.fileno()

    def fileno(self):
        return self.sock.fileno()

    def set_handler_id(self, handler_id):
        self.handler_id = handler_id

    def wrap_socket(self, host):
        if self.ssl_enable or self.is_closed():
            return
        ctx = ssl.create_default_context()
        if self.tag == 'client':
            certfile = CertificateHelper.generate_cert(host)
            ctx.load_cert_chain(certfile, keyfile=CertificateHelper.certkey)
            ctx.check_hostname = False
            # In server mode, no certificate is requested from the client
            ctx.verify_mode = ssl.CERT_NONE
            # do_handshake_on_connect should only be used for blocking sockets,
            # so we need to set blocking and set unblocking (and the events)
            # after the handshake is done
            self.sock.setblocking(True)
            self.sock = ctx.wrap_socket(
                self.sock,
                do_handshake_on_connect=True,
                server_side=True)
            self.sock.setblocking(False)
        else:
            self.sock.setblocking(True)
            self.sock = ctx.wrap_socket(
                self.sock,
                server_hostname=host,
                do_handshake_on_connect=True)
            self.sock.setblocking(False)
        self.ssl_enable = True

    def recv(self, buffer_size: int = BUFFER_SIZE):
        if self.is_closed():
            return None
        data = b''
        try:
            while True:
                buf = self.sock.recv(buffer_size)
                if len(buf) == 0:
                    break
                data += buf
        except (ssl.SSLWantReadError, BlockingIOError) as e:
            logger.error(e)
            if len(data) == 0:
                raise e
        logger.info('Receive %d bytes, %s fd %d',
                    len(data), self.tag, self.fileno())
        if len(data) == 0:
            return None
        return data

    def close(self):
        logger.info('Close %s fd %d', self.tag, self.fileno())
        self.sock.close()
        self.read_closed = False
        self.closed = True

    def flush_close(self):
        if self.has_buffer():
            self.read_closed = True
        else:
            self.close()

    def flush(self):
        if self.is_closed():
            return 0
        n = 0
        if len(self.buffer) > 0:
            n = self.sock.send(self.buffer)
            if self.tag == 'upstream':
                logger.debug('upstream %d, send: %s',
                             self.sock.fileno(), self.buffer[:n])
            self.buffer = self.buffer[n:]
        logger.info('Send %d bytes, %s fd %d', n, self.tag, self.fileno())
        if self.read_closed and not self.has_buffer():
            self.close()
        return n

    def push_buffer(self, data: bytes):
        self.buffer += data

    def has_buffer(self):
        return len(self.buffer) > 0

    def is_closed(self):
        return self.closed

    def is_read_closed(self):
        return self.read_closed

