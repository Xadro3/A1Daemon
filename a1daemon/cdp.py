"""Minimal loopback-only CDP WebSocket transport (Python standard library)."""
import base64
import hashlib
import json
import os
import socket
import struct
import urllib.parse


class CDP:
    def __init__(self, url):
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != 'ws' or parsed.hostname not in ('127.0.0.1', 'localhost', '::1'):
            raise ValueError('CDP connections must use a local WebSocket')
        self.socket = socket.create_connection((parsed.hostname, parsed.port or 80), timeout=8)
        self.buffer = b''
        self.sequence = 0
        key = base64.b64encode(os.urandom(16)).decode()
        path = parsed.path + ('?' + parsed.query if parsed.query else '')
        request = f'GET {path} HTTP/1.1\r\nHost: {parsed.netloc}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n'
        self.socket.sendall(request.encode())
        while b'\r\n\r\n' not in self.buffer:
            chunk = self.socket.recv(4096)
            if not chunk:
                raise ConnectionError('CDP closed during handshake')
            self.buffer += chunk
            if len(self.buffer) > 65536:
                raise ConnectionError('Invalid CDP handshake')
        headers, self.buffer = self.buffer.split(b'\r\n\r\n', 1)
        expected = base64.b64encode(hashlib.sha1((key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest())
        fields = {k.strip().lower(): v.strip() for k, v in (line.split(b':', 1) for line in headers.split(b'\r\n')[1:] if b':' in line)}
        if b' 101 ' not in headers.split(b'\r\n')[0] or fields.get(b'sec-websocket-accept') != expected:
            self.close()
            raise ConnectionError('CDP WebSocket handshake rejected')

    def close(self):
        self.socket.close()

    def exact(self, count):
        while len(self.buffer) < count:
            chunk = self.socket.recv(max(4096, count - len(self.buffer)))
            if not chunk:
                raise ConnectionError('CDP disconnected')
            self.buffer += chunk
        result, self.buffer = self.buffer[:count], self.buffer[count:]
        return result

    def send(self, data, opcode=1):
        mask = os.urandom(4)
        length = len(data)
        prefix = bytes([0x80 | opcode])
        prefix += bytes([0x80 | length]) if length < 126 else bytes([0xFE]) + struct.pack('!H', length) if length < 65536 else bytes([0xFF]) + struct.pack('!Q', length)
        self.socket.sendall(prefix + mask + bytes(value ^ mask[i % 4] for i, value in enumerate(data)))

    def receive(self):
        fragments = bytearray()
        while True:
            first, second = self.exact(2)
            length = second & 0x7f
            if length == 126:
                length = struct.unpack('!H', self.exact(2))[0]
            elif length == 127:
                length = struct.unpack('!Q', self.exact(8))[0]
            if length > 8 * 1024 * 1024:
                raise ConnectionError('CDP frame exceeds limit')
            mask = self.exact(4) if second & 0x80 else None
            payload = self.exact(length)
            if mask:
                payload = bytes(value ^ mask[i % 4] for i, value in enumerate(payload))
            opcode = first & 0x0f
            if opcode == 8:
                raise ConnectionError('CDP closed the connection')
            if opcode == 9:
                self.send(payload, 10)
                continue
            if opcode == 10:
                continue
            fragments.extend(payload)
            if len(fragments) > 8 * 1024 * 1024:
                raise ConnectionError('CDP message exceeds limit')
            if first & 0x80:
                return json.loads(fragments)

    def call(self, method, params, session_id=None):
        self.sequence += 1
        message_id = self.sequence
        message = {'id': message_id, 'method': method, 'params': params}
        if session_id:
            message['sessionId'] = session_id
        self.send(json.dumps(message).encode())
        while True:
            response = self.receive()
            if response.get('id') == message_id:
                if 'error' in response:
                    raise RuntimeError(str(response['error']))
                result = response.get('result', {})
                if result.get('exceptionDetails'):
                    raise RuntimeError(str(result['exceptionDetails']))
                return result
