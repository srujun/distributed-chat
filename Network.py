from __future__ import print_function

import logging
import socket
import sys
import threading

class Network:
    PORT = 1337

    def __init__(self, nodelist, timeout=2):
        logging.basicConfig(filename='network.log',level=logging.DEBUG)

        self.nodelist = nodelist
        self.alive = {}

        oldtimeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(timeout)

        for node, port in nodelist:
            logging.debug('Connecting to ' + node + ':' + str(port))
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                sock.connect((node, port))
            except (socket.timeout, socket.error) as e:
                logging.debug('Could not connect')
                pass
            else:
                logging.debug('Connection successful!')
                self.alive[socket.gethostbyname(node)] = [sock, port]
        logging.debug('# alive = ' + str(len(self.alive)))
        logging.debug(str(self.alive))

        socket.setdefaulttimeout(oldtimeout)

        # start the server thread
        self.server = threading.Thread(target=self.server_thread)
        self.server.daemon = True
        self.server.start()


    def server_thread(self):
        ss = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ss.bind(('', Network.PORT))
        ss.listen(10)
        logging.debug('Starting server...')
        while True:
            clientsocket, addr = ss.accept()
            ip, port = addr
            logging.debug('Got connection from ' + ip)
            self.alive[socket.gethostbyname(addr[0])] = [clientsocket, port]


    def send_msg(self, msg):
        for host in self.alive.keys():
            totalsent = 0
            while totalsent < len(msg):
                sent = self.alive[host][0].send(msg[totalsent:])
                if sent == 0:
                    # lost connection
                    del self.alive[host]
                totalsent += sent


    def close(self):
        for host in self.alive.keys():
            self.alive[host][0].close()
