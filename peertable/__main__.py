import peertable
import base64

class TestApp(peertable.PeerApplication):
    def receive(self, server, client, message):
        print(">+ + + + +\nReceived message!\nSender ID: {}\nMessage type: {}\nPayload length: {}\nPayload in Base64: {}\n- - - - -<".format(client.id, message.message_type, len(message.payload), base64.b64encode(message.payload).decode('utf-8')))

if __name__ == "__main__":
    print("Insert your new peer's listen port: (defaults to 2912)")
    port = int(input() or 2912)
    
    print()
    print("Insert your machine's public IP address (so others can connect to you, etc):")
    
    my_addr = input()
    
    print()
    print("Insert this server's public port, in case you use a tunnel or port forward (or none otherwise):")
    
    my_port = int(input() or port)
    
    s = peertable.PeerServer(my_addr, port=port, remote_port=my_port)
    s.start_loop()
    s.register_app(TestApp())
    
    print()
    print("My port: " + str(s.port))
    print("My ID: " + str(s.id))
    print()
    print("Insert target IP:port addresses, separated by space:")
    
    addrs = input()
    
    for addr in addrs.split(' '):
        try:    
            addr = addr.split(':')
        
            if len(addr) < 2:
                raise ValueError("-----")
            
            addr[1] = int(addr[1])
            s.connect(tuple(addr))
            
        except ValueError:
            pass