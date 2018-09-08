import traceback
import time
import time
import random
import string
import io
import socket
import warnings
import struct
import threading
import requests


class PeerApplication(object):
    def receive(self, server, client, message):
        pass
        
    def on_registered(self, server):
        pass
        
    def connected(self, server, client):
        pass

    def disconnected(self, server, client):
        pass

class NCMHandler(object):
    MSG_TYPE = "        "

    def __init__(self, server):
        self.server = server
    
    def handle(self, client, message):
        pass
        
    def should_handle(self, client, message):
        return message.message_type.upper()[:8].rstrip(' ') == type(self).MSG_TYPE.upper()[:8].rstrip(' ')

class NCMDisconnectHandler(NCMHandler):
    MSG_TYPE = "EXITPEER"

    def handle(self, client, message):
        server.remove_id(client.id)
        
        for app in self.server.applications:
            app.disconnected(self.server, client)

class NCMPathfindHandler(NCMHandler):
    MSG_TYPE = "PATHFIND"

    def handle(self, client, message):
        requester_ip, requester_port, request_id, target_id, closed = [x.decode('utf-8') for x in message.payload.split(b':')]
        closed = [x for x in closed.split('#') if x]
        closed.append(client.id)
        
        if self.server.id == target_id:
            self.server.connect((requester_ip, int(requester_port)))
        
        else:
            for c in self.server.clients:
                if c.id not in closed:
                    c.send(Message(False, 'PATHFIND', '{}:{}:{}:{}:{}'.format(requester_ip, requester_port, request_id, target_id, '#'.join(closed))))
        
class NCMIdentifyHandler(NCMHandler):
    MSG_TYPE = "IDENTIFY"

    def handle(self, client, message):
        client.id = message.payload.decode('utf-8')

class NCMRequestIdentifyHandler(NCMHandler):
    MSG_TYPE = "IDENTREQ"

    def handle(self, client, message):
        client.send(Message(False, "IDENTIFY", self.server.id))

class Message(object):
    def __init__(self, app_level, message_type, payload=b""):
        self.app_level = app_level
        self.message_type = message_type
        self.payload = payload
        
        if type(self.payload) is str:
            self.payload = payload.encode('utf-8')

    def serialize(self):
        message_type = self.message_type[:8] + " " * (8 - min(8, len(self.message_type)))
        return  (b"Y" if self.app_level else b"N") + message_type.encode('utf-8') + struct.pack('Q', len(self.payload)) + self.payload
        
class MessageDeserializer(object):
    def __init__(self):
        self.msg = io.BytesIO()
    
    def write(self, msg):
        pos = self.msg.tell()
        self.msg.write(msg)
        self.msg.seek(pos)
    
    def _read_one(self):
        appl = self.msg.read(1)
        
        if appl == b'':
            return
        
        app_level = appl == b"Y"
        
        if not app_level and appl != b"N":
            raise ValueError('Bad message received at {}: invalid ALM/NCM classification boolean byte! (expected Y (0x59) or N (0x4E), but got {} (0x{}))'.format(time.time(), appl, appl.hex().upper()))
            
        msg_type = self.msg.read(8).decode('utf-8')
        
        if len(msg_type) < 8:
            raise ValueError("Bad message received at {}: insufficient characters for header - message too small! ({} bytes, minimum 17)".format(time.time(), 1 + len(msg_type)))
            
        payload_len = self.msg.read(8)
        
        if len(payload_len) < 8:
            raise ValueError("Bad message received at {}: insufficient characters for header - message too small! ({} bytes, minimum 17)".format(time.time(), 9 + len(payload_len)))
    
        payload_len, = struct.unpack('Q', payload_len)
        payload = self.msg.read(payload_len)
        
        if len(payload) < payload_len:
            self.msg.seek(self.msg.tell() - len(payload))
            warnings.warn("Bad message received at {}: insufficient characters for payload - message too small! (expected {} payload bytes, got {})".format(time.time(), payload_len + len(payload)))
            return
            
        return Message(app_level, msg_type, payload)
        
    def __iter__(self):
        return self
        
    def __next__(self):
        try:
            r = self._read_one()
            
            if r is None:
                raise StopIteration
                
            return r
            
        except ValueError:
            traceback.print_exc()
            raise StopIteration
        
class PeerClient(object):
    def __init__(self, server, address, _socket=None, id=None):
        self.server = server
        self.id = id
        self.deserializer = MessageDeserializer()
        
        if type(address) is str:
            self.address = tuple(address.split(':')[:2])
            self.address = (self.address[0], int(self.address[1]))
            
        else:
            self.address = address
        
        self.socket = _socket
        
        if self.socket is None:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect(self.address)
            self.socket.setblocking(0)
        
        if self.id is None:
            self.send(Message(False, "IDENTREQ"))
            
    def disconnect(self):
        self.send(Message(False, "EXITPEER"))
        self.server.clients.remove(self)
        
        for app in self.server.applications:
            app.disconnected(self.server, self)
        
    def send(self, msg):
        data = msg.serialize()
        st = io.BytesIO(data)
        st.seek(0)
        
        try:
            while st.tell() < len(data) - 1:
                self.socket.sendall(st.read(2048))
                
        except ConnectionAbortedError:
            self.server.clients.remove(self)
        
            for app in self.server.applications:
                app.disconnected(self.server, self)
        
    def tick(self):
        try:
            data = self.socket.recv(2048)
            self._receive(data)
            
        except socket.error:
            pass
        
    def _receive(self, data):
        self.deserializer.write(data)
        self.server.on_receive(self)
        
class RoutePending(object):
    def __init__(self, id, msg, target):
        self.id = id
        self.time = time.time()
        self.msg = msg
        self.target = target
        
class PeerServer(object):
    DEFAULT_HANDLERS = (NCMDisconnectHandler, NCMIdentifyHandler, NCMPathfindHandler, NCMRequestIdentifyHandler)

    def __init__(self, my_addr, id=None, message_timeout=60, port=2912, remote_port=None):
        self.id = id
        
        if self.id is None:
            self.id = ''.join([random.choice(string.ascii_letters + string.digits) for _ in range(25)])
        
        self.message_timeout = message_timeout
        self.clients = []
        self.ncm_handlers = [d(self) for d in type(self).DEFAULT_HANDLERS]
        self.pending = []
        self.applications = []
        self.port = port
        self.remote_port = remote_port or port
            
        self.address = my_addr
        
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind(("0.0.0.0", port))
        self.socket.listen(5)
        self.socket.setblocking(0)
        
    def register_app(self, app):
        self.applications.append(app)
        app.on_registered(self)
        
    def connect(self, address):
        self.clients.append(PeerClient(self, address))
        
    def not_found(self, p):
        warnings.warn("Warning: route to {} not found! (pending message of PMID {})".format(p.target, p.id))
        
    def send_id(self, id, msg):
        cn = tuple(self.clients)    # > here to prevent skipping clients that occupy
                                    #   the slots of popped ones, in case any are
                                    #   popped               
                              
        for c in cn:
            if c.id == id:
                # Client found; send and return.
                c.send(msg)
                return
                
        # Client was not found in local table. Time to pathfind.
        r = RoutePending(''.join([random.choice(string.ascii_letters + string.digits) for _ in range(50)]), msg, id)
        self.pending.append(r)
        m = Message(False, "PATHFIND", '{}:{}:{}:{}:'.format(self.address, self.remote_port, r.id, id))
        
        for c in self.clients:
            c.send(m)
            
    def loop(self, ticks_per_second=60):
        _delay = 1 / ticks_per_second
    
        while True:
            self.tick()
            time.sleep(_delay)
            
    def start_loop(self):
        threading.Thread(target=self.loop).start()
            
    def tick(self):
        for p in self.pending:
            if p.target in [c.id for c in self.clients]:
                self.send_id(p.target, p.msg)
                self.remove_pending(p.id)
        
            elif time.time() - p.time > self.message_timeout:
                self.not_found(p.id)
                self.remove_pending(p.id)
    
        for c in self.clients:
            c.tick()
            
        try:
            conn, addr = self.socket.accept()
            c = PeerClient(self, addr, conn)
            self.clients.append(c)
            
            for app in self.applications:
                app.connected(self, c)
            
        except socket.error:
            pass
        
    def disconnect(self):
        for c in self.clients:
            c.disconnect()
        
    def remove_id(self, id):
        self.clients = [c for c in self.clients if c.id != id]
         
    def remove_pending(self, id):
        self.pending = [p for p in self.pending if p.id != id]
        
    def on_receive(self, client):
        for msg in client.deserializer:
            if msg.app_level:
                for app in self.applications:
                    app.receive(self, client, msg)
            
            else:
                for handler in self.ncm_handlers:
                    if handler.should_handle(client, msg):
                        handler.handle(client, msg)