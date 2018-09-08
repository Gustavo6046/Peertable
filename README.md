# Peertable

Welcome to Peertable! This project is an infrastructural peer-to-peer
networking library for Python 3. You can also use it in standalone
mode, although that is for little use other than connecting
existing peers and networks (so they can find each other - but
once they do, you don't need that anymore!).

## Creating a Bridge Peer

The default (mostly demonstrative) Peertable application will,
by default, only log messages given to it, but, like any peer, will,
yes, serve to an actual purpose: acting as a bridge between peers, or
possibly even networks!

To use the default application, use:

    python3 -i -m peertable
    
Then, insert your listen port, public IP address (preferentially either
outside a NAT or port forwarded), and external port (if behind a tunnel
of sorts, e.g. ngrok), in order. The external port is optional.

Then, insert a space-separated list of initial peers to connect to (or
nothing, if none).

Et voilá! You are now connected, and in the interactive prompt. It might
seem like it's idle, but it is connecting to the target peers! And it's
sending identificatoin requests (and identifying your server as well, by
extension). You can now use the **Send Commands**:

    >>> [c.id for c in s.clients]
    ['fc4h0MwGznaAqObYDWMXUiAAZ']
    
    >>> for c in s.clients:
    ...     s.send_id(c.id, peertable.Message(True, "TESTMESG", "Hello! If you are reading this, then a human is behind the recipient peer of this message, i.e. YOU! Your ID: " + c.id))
    
In this example, the other side would see:

    >+ + + + +
    Received message!
    Sender ID: p8vM6FqyBGzm0Sdnr6XCDoZdy
    Message type: TESTMESG
    Payload length: 135
    Payload in Base64: SGVsbG8hIElmIHlvdSBhcmUgcmVhZGluZyB0aGlzLCB0aGVuIGEgaHVtYW4gaXMgYmVoaW5kIHRoZSByZWNpcGllbnQgcGVlciBvZiB0aGlzIG1lc3NhZ2UsIGkuZS4gWU9VISBZb3VyIElEOiBmYzRoME13R3puYUFxT2JZRFdNWFVpQUFa
    - - - - -<
    
The payload is the message you gave, in the third argument in the call to `peertable.Message`, which return value, in turn, is the 2nd argument to the call to `s.send_id`.

## Using the Library

For a good example, check this out:

    import peertable
    import random
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
                
And before you ask, yes, this is the script that is run when you do `python3 -i -m peertable`.