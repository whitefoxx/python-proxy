#!/usr/local/bin/python3

import socket
import selectors
import logging


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
file_handler = logging.FileHandler('proxy.log')
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s: %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

selector = selectors.DefaultSelector()


class Request:

    def __init__(self, req_bytes):
        self.method = 'NONE'
        if req_bytes.startswith(b'CONNECT'):
            self.method = 'CONNECT'
            ts = req_bytes.split(b' ')
            host, port = ts[1].split(b':')
            self.host = host
            self.port = int(port)
        else:
            req_str = req_bytes.decode()
            lines = req_str.split('\r\n')
            first_line = lines[0]
            ts = first_line.split(' ')
            self.method, self.path, self.protocal = ts
            self.host = ''
            self.port = 80
            if self.path.startswith('https://'):
                self.port = 443
            self.headers = {}
            for line in lines[1:]:
                if ':' in line:
                    h, v = line.split(':')
                    if h.lower() == 'host':
                        self.host = v.strip()
                    self.headers[h.strip()] = v.strip()
            if not self.host:
                self.host = self.path.split('/')[2]


class Connection:

    def __init__(self, sock, addr):
        self.sock = sock
        self.addr = addr
        self.input = b''
        self.output = b''
        self.select_event = 0
        self.closed = False

    def close(self):
        self.sock.close()
        self.closed = True
        self.select_event = 0
        # For debug: save the client request or the upstream response
        logger.debug(self.input)
        self.input = b''
        self.output = b''

    def get_input(self):
        return self.input

    def get_output(self):
        return self.output

    def read(self):
        recv_bytes = self.sock.recv(4096)
        self.input += recv_bytes
        return recv_bytes

    def write(self):
        sent_bytes = b''
        if self.has_output():
            n = self.sock.send(self.output)
            if n > 0:
                sent_bytes = self.output[:n]
                self.output = self.output[n:]
        return sent_bytes

    def push_data(self, data_bytes):
        self.output += data_bytes

    def get_request(self):
        i = self.input.find(b'\r\n\r\n')
        req = None
        if i != -1:
            i += 4
            req_bytes = self.input[:i]
            req = Request(req_bytes)
            if req.method == 'CONNECT':
                self.input = self.input[i:]
        return req

    def got_complete_requset(self):
        return self.input.find(b'\r\n\r\n') != -1

    def select_on_write(self):
        return self.select_event & selectors.EVENT_WRITE

    def select_on_read(self):
        return self.select_event & selectors.EVENT_READ

    def has_input(self):
        return len(self.input) > 0

    def has_output(self):
        return len(self.output) > 0


class HttpProxyPipe:

    def __init__(self, downstream_conn, upstream_conn):
        self.downstream_conn = downstream_conn
        self.upstream_conn = upstream_conn

    def setup_upstream(self):
        req = self.downstream_conn.get_request()
        if not req: return
        s = socket.create_connection((req.host, req.port))
        s.setblocking(False)
        self.upstream_conn = Connection(s, '')
        self.set_event(self.upstream_conn, selectors.EVENT_READ)
        if req.method == 'CONNECT':
            resp = b'HTTP/1.1 200 Connection Established\r\n\r\n'
            self.downstream_conn.push_data(resp)
        # if there bytes left in downstream after dequeueing the request
        # pipe the left bytes to the content filter
        left_bytes = self.downstream_conn.get_input()
        if left_bytes:
            self.pipe_to_content_filter(left_bytes, 'downstream')

    def pipe_to_content_filter(self, content_bytes, from_who):
        if from_who == 'downstream':
            self.upstream_conn.push_data(content_bytes)
        elif from_who == 'upstream':
            self.downstream_conn.push_data(content_bytes)

    def read_from(self, conn):
        recv_bytes = conn.read()
        if conn == self.downstream_conn:
            if self.upstream_conn is not None:
                self.pipe_to_content_filter(recv_bytes, 'downstream')
            elif self.downstream_conn.got_complete_requset():
                self.setup_upstream()
        else:
            self.pipe_to_content_filter(recv_bytes, 'upstream')
        if self.upstream_conn is not None \
                and self.upstream_conn.has_output() \
                and not self.upstream_conn.select_on_write():
            self.set_event(self.upstream_conn, selectors.EVENT_WRITE)
        if self.downstream_conn.has_output() \
                and not self.downstream_conn.select_on_write():
            self.set_event(self.downstream_conn, selectors.EVENT_WRITE)
        return recv_bytes

    def write_to(self, conn):
        sent_bytes = conn.write()
        if not conn.has_output():
            self.unset_event(conn, selectors.EVENT_WRITE)
        return sent_bytes

    def set_event(self, conn, event):
        if conn.closed:
            return
        if conn.select_event == 0:
            conn.select_event |= event
            selector.register(conn.sock, conn.select_event, data=self)
        else:
            conn.select_event |= event
            selector.modify(conn.sock, conn.select_event, data=self)

    def unset_event(self, conn, event):
        if conn.closed:
            return
        conn.select_event &= (~event);
        if conn.select_event == 0:
            selector.unregister(conn.sock)
        else:
            selector.modify(conn.sock, conn.select_event, data=self)

    def get_connection_of_socket(self, s):
        if self.downstream_conn \
                and self.downstream_conn.sock.fileno() == s.fileno():
            return self.downstream_conn
        if self.upstream_conn \
                and self.upstream_conn.sock.fileno() == s.fileno():
            return self.upstream_conn

    def close_connection(self, conn):
        if conn.select_event != 0:
            selector.unregister(conn.sock)
        conn.close()


class ProxyServer:

    def __init__(self, conf):
        self.port = conf.port
        self._setup_socket()

    def _setup_socket(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind(('127.0.0.1', self.port))
        self.sock.listen()
        self.sock.setblocking(False)
        selector.register(self.sock, selectors.EVENT_READ, data=None)

    def accept_connection(self, sock):
        s, addr = sock.accept()
        s.setblocking(False)
        downstream_conn = Connection(s, addr)
        p = HttpProxyPipe(downstream_conn, None)
        p.set_event(downstream_conn, selectors.EVENT_READ)
        logger.info('Accept connection: socket(%d)', s.fileno())

    def handle_connection(self, key, mask):
        s = key.fileobj
        pipe = key.data
        conn = pipe.get_connection_of_socket(s)
        if mask & selectors.EVENT_READ:
            recv_bytes = pipe.read_from(conn)
            if not recv_bytes:
                logger.info("Close socket: %d", s.fileno())
                pipe.close_connection(conn)
        if mask & selectors.EVENT_WRITE:
            pipe.write_to(conn)

    def forever_run(self):
        while True:
            events = selector.select(timeout=None)
            for key, mask in events:
                if key.data is None:
                    self.accept_connection(key.fileobj)
                else:
                    self.handle_connection(key, mask)
