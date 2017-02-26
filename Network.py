from __future__ import print_function

import json
import logging
import pickle
import socket
import sys
import threading
import time
import uuid

class Network:
    PORT = 13337

    def __init__(self, nodelist, disp_func, timeout=1):
        logging.basicConfig(filename='network.log',level=logging.DEBUG)

        self.nodelist = nodelist
        # map from host ip (str) -> [socket, port]
        self.alive = {}

        # counter used for ISIS ordering
        self.counter = 0

        oldtimeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(timeout)

        self.disp_func = disp_func

        # start the server thread
        self.server = threading.Thread(target=self.server_thread)
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


    def server_thread(self):
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

                self.start_receivers(receivers=[ip])


    def start_receivers(self, receivers=[]):
        if len(receivers) == 0:
            receivers = self.alive.keys()

        for host in receivers:
            receiver = threading.Thread(target=self.recv_msg,
                                        args=(host, self.disp_func))
            receiver.daemon = True
            receiver.start()


    def bcast_msg(self, msg):
        threads = []
        for host in self.alive.keys():
            t = threading.Thread(target=self.send_msg, args=(msg, host))
            threads.append(t)
            t.start()

        for thread in threads:
            thread.join()


    def send_msg(self, msg, host):
        logging.debug('Sending to {}: {}'.format(host, str(msg)))

        pickled = pickle.dumps(msg)

        totalsent = 0
        while totalsent < len(pickled):
            try:
                sent = self.alive[host][0].send(pickled[totalsent:])
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
                pickled = self.alive[host][0].recv(512)
                if not pickled:
                    # TODO: show offline at the right time
                    callback(host + " went offline...")
                    del self.alive[host]
                    break

                message = pickle.loads(pickled)
                if type(message) is not Message:
                    logging.warning('Unpickling received msg unsuccessful: ' + \
                                    pickled)
                else:
                    callback(message)
                time.sleep(0.5)

            except socket.timeout:
                time.sleep(1)
                continue


    def close(self):
        for host in self.alive.keys():
            self.alive[host][0].close()


class Message:
    # msgtype can be one of "chat", "proposal", "final"
    CHAT = "chat"
    PROPOSAL = "proposal"
    FINAL = "final"

    def __init__(self, msgtype, msgid=None, text='', username='', proposed=-1, final=-1):
        self.msgtype = msgtype
        if not msgid:
            self.msgid = uuid.uuid1()
        else:
            self.msgid = msgid
        self.text = text
        self.username = username
        self.proposed = proposed
        self.final = final

        # raise TypeError('Message type unknown' + str(msgtype))
