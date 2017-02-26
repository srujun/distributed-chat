from __future__ import print_function

import json
import logging
import socket
import sys
import threading
import time
import uuid

class Network:
    PORT = 13337

    def __init__(self, nodelist, ci, timeout=1):
        logging.basicConfig(filename='network.log',level=logging.DEBUG)

        self.nodelist = nodelist
        self.alive = {}

        # counter used for ISIS ordering
        self.counter = 0

        oldtimeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(timeout)

        # start the server thread
        self.server = threading.Thread(target=self.server_thread, args=(ci,))
        self.server.daemon = True
        self.server.start()

        for node, port in nodelist:
            logging.debug('Connecting to ' + node + ':' + str(port))
            if node == socket.gethostname():
                logging.debug('Not gonna connect to myself...')
                continue
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

        # socket.setdefaulttimeout(oldtimeout)


    def server_thread(self, ci):
        ss = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ss.bind(('', Network.PORT))
        ss.listen(10)
        logging.debug('Starting server...')
        while True:
            try:
                clientsocket, addr = ss.accept()
            except socket.timeout:
                pass
            else:
                ip, port = addr
                logging.debug('Got connection from ' + ip)
                self.alive[ip] = [clientsocket, port]

                # start the receiver thread for this new connection
                receiver = threading.Thread(target=self.recv_msg, args=(ip, ci.add_message))
                receiver.daemon = True
                receiver.start()


    def bcast_msg(self, msg):
        jsonsend = {
            'message': msg,
            'counter': None,
            'msgid': uuid.uuid1().hex
        }
        jsonmsg = json.dumps(jsonsend)

        threads = []
        for host in self.alive.keys():
            t = threading.Thread(target=self.send_msg, args=(jsonmsg, host))
            threads.append(t)
            t.start()

        for thread in threads:
            thread.join()


    def send_msg(self, msg, host):
        logging.debug('Sending "' + msg + '" to ' + host)
        totalsent = 0
        while totalsent < len(msg):
            try:
                sent = self.alive[host][0].send(msg[totalsent:])
            except socket.error:
                del self.alive[host]
                logging.debug(host + ' went offline...')
                break
            if sent == 0:
                # lost connection
                logging.debug('Could not send msg, lost connection!')
                del self.alive[host]
            totalsent += sent


    def recv_msg(self, host, callback):
        while True:
            try:
                jsonmsg = self.alive[host][0].recv(512)
                if not jsonmsg:
                    time.sleep(1)
                    continue

                jsonrecv = json.loads(jsonmsg)
                callback(jsonrecv['message'])
                time.sleep(0.5)

            except socket.timeout:
                time.sleep(1)
                continue


    def close(self):
        for host in self.alive.keys():
            self.alive[host][0].close()
