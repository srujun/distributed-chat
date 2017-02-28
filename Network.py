from __future__ import print_function

import copy
import cPickle
from cStringIO import StringIO
from datetime import datetime
import logging
from operator import add
import socket
import sys
import threading
import time
import uuid

class Network:
    PORT = 13337

    def __init__(self, nodelist, disp_func, timeout=1):
        # logging.basicConfig(filename='network.log',level=logging.DEBUG)

        self.nodelist = nodelist

        # map from host ip (str) -> socket
        self.alive = {}
        self.alive_mutex = threading.RLock()

        # counter used for ISIS ordering
        self.counter = 0
        self.counter_mutex = threading.RLock()

        # message queue for ISIS ordering
        self.msgqueue = []
        self.queue_mutex = threading.Lock()

        # unique identifier for appending to each priority number
        # it is the sum of the digitis of the IP address
        self.uid = reduce(add, map(int, Network.get_ip().split('.')))

        oldtimeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(timeout)

        self.disp_func = disp_func

        # start the server thread
        self.server = threading.Thread(target=self.server_thread)
        self.server.daemon = True
        self.server.start()

        for node, port in nodelist:
            logging.info('Connecting to ' + node + ':' + str(port))
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
                logging.info('Connection successful at {}'.format(datetime.now()))

                self.alive_mutex.acquire()
                self.alive[socket.gethostbyname(node)] = sock
                self.alive_mutex.release()

        logging.debug('# alive = ' + str(len(self.alive)))
        logging.debug(str(self.alive))

        # start the delivery thread
        self.delivery = threading.Thread(target=self.do_delivery)
        self.delivery.daemon = True
        self.delivery.start()

        # socket.setdefaulttimeout(oldtimeout)


    @classmethod
    def get_ip(cls):
        return socket.gethostbyname(socket.gethostname())


    @classmethod
    def merge_float(cls, num1, num2):
        return float('{}.{}'.format(num1, num2))


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
                logging.debug('Got connection from {} at {}'.format(
                    ip, datetime.now()
                ))
                self.disp_func('{} has come online!'.format(ip))

                self.alive_mutex.acquire()
                self.alive[ip] = clientsocket
                self.alive_mutex.release()
                self.start_receivers(receivers=[ip])


    def start_receivers(self, receivers=[]):
        if len(receivers) == 0:
            receivers = self.alive.keys()

        for host in receivers:
            receiver = threading.Thread(target=self.recv_msg,
                                        args=(host, self.handle_message))
            receiver.daemon = True
            receiver.start()


    def recv_msg(self, host, callback):
        while True:
            try:
                self.alive_mutex.acquire()
                try:
                    sock = self.alive[host]
                except KeyError:
                    logging.debug('{} died while in recv!'.format(host))
                    self.alive_mutex.release()
                    break
                self.alive_mutex.release()

                pickled = sock.recv(2048)
                numbytes = len(pickled)
                logging.debug('Recv got {} bytes'.format(numbytes))

                if numbytes == 0:
                    self.handle_crash(host)
                    break

                pbuf = StringIO(pickled)
                while pbuf.tell() < numbytes:
                    message = cPickle.load(pbuf)
                    self.handle_message(message)

                time.sleep(0.5)

            except socket.timeout:
                time.sleep(1)
                continue
            except socket.error:
                self.handle_crash(host)
                break


    def bcast_msg(self, msg, destinations=[], wait=True):
        logging.debug('New bcast {}'.format(msg))
        threads = []
        is_all_hosts = False

        if len(destinations) == 0:
            is_all_hosts = True
            destinations = self.alive.keys()

        # add msg to msgqueue if it is a new chat message
        if msg.msgtype == Message.CHAT:
            # qmsg = copy.deepcopy(msg)
            qmsg = Message(Message.CHAT, msg.origin, text=msg.text,
                           msgid=msg.msgid, username=msg.username)
            qmsg.alive_set = msg.alive_set.copy()

            self.counter_mutex.acquire()
            self.counter += 1
            logging.debug('Incrementing counter to {}'.format(self.counter))
            qmsg.priority = Network.merge_float(self.counter, self.uid)
            self.counter_mutex.release()

            qmsg.deliverable = False
            qmsg.alive_set = set(self.alive.keys())

            self.queue_mutex.acquire()
            self.msgqueue.append(qmsg)
            self.msgqueue.sort(key=lambda m: m.priority)
            logging.debug('Queue: {}'.format(self.msgqueue))
            self.queue_mutex.release()

        if is_all_hosts:
            self.alive_mutex.acquire()
        for host in destinations:
            t = threading.Thread(target=self.send_msg, args=(msg, host))
            threads.append(t)
            t.start()
        if is_all_hosts:
            self.alive_mutex.release()

        if wait:
            for thread in threads:
                thread.join()


    def send_msg(self, msg, host):
        logging.debug('Sending to {}: {}'.format(host, str(msg)))
        logging.info('SEND time={}, msg={}'.format(datetime.now(), msg))

        pickled = cPickle.dumps(msg, cPickle.HIGHEST_PROTOCOL)
        totalsent = 0

        self.alive_mutex.acquire()
        try:
            sock = self.alive[host]
        except KeyError:
            logging.debug('{} died while in send!'.format(host))
            self.alive_mutex.release()
            return
        self.alive_mutex.release()

        while totalsent < len(pickled):
            try:
                logging.debug('Sending bytes...')
                sent = sock.send(pickled[totalsent:])
            except socket.error:
                self.handle_crash(host)
                break
            if sent == 0:
                logging.debug('Could not send msg, lost connection!')
                self.handle_crash(host)
                break

            totalsent += sent
        logging.debug('Send successful {} bytes, '
                      'msg: {}'.format(totalsent, msg))


    def handle_message(self, message):
        logging.debug('Handle message: {}'.format(message))
        logging.info('HANDLE time={}, msg={}'.format(datetime.now(), message))

        # normal string display
        if isinstance(message, str):
            logging.debug('Display msg: ' + message)
            self.disp_func(message)
            return

        # need to respond with a proposed priority
        if message.msgtype == Message.CHAT:
            logging.debug('Got NEW msg')
            proposal = Message(Message.PROPOSAL, Network.get_ip(),
                               msgid=message.msgid)
            self.counter_mutex.acquire()
            self.counter += 1
            logging.debug('Incrementing counter to {}'.format(self.counter))
            proposal.priority = Network.merge_float(self.counter, self.uid)
            self.counter_mutex.release()

            message.priority = proposal.priority
            message.deliverable = False

            # store msg in queue with the proposed priority
            self.queue_mutex.acquire()
            self.msgqueue.append(message)
            self.msgqueue.sort(key=lambda m: m.priority)
            logging.debug('Queue: {}'.format(self.msgqueue))
            self.queue_mutex.release()

            # send the proposal back to the sender
            self.bcast_msg(proposal, destinations=[message.origin], wait=False)

        # wait until we receive proposals from everyone
        elif message.msgtype == Message.PROPOSAL:
            logging.debug('Got proposal')

            # get the original msg from the queue
            self.queue_mutex.acquire()
            try:
                orig = next(m for m in self.msgqueue if m.msgid == message.msgid)
            except StopIteration:
                # TODO: check this release
                self.queue_mutex.release()
                logging.warning('Bogus proposal. ID: {}'.format(message.msgid))
                return

            # TODO: check this release
            # self.queue_mutex.release()

            # add this proposal to the original message's proposals set
            orig.proposals_mutex.acquire()
            orig.proposals.add(message)
            orig.proposals_mutex.release()
            # update the counter
            self.counter_mutex.acquire()
            logging.debug('Counter update from {}'.format(self.counter))
            self.counter = int(max(self.counter, message.priority)) + 1
            logging.debug('Counter update to {}'.format(self.counter))
            self.counter_mutex.release()

            # if we have received proposals from everyone, mark as deliverable
            # and remulticast it
            # we know if everyone has sent proposals if the set of nodes that
            # have sent a proposal equals the intersection of the set of nodes
            # alive at send time and the set of nodes alive now

            self.alive_mutex.acquire()
            alive_rn = set(self.alive.keys())
            self.alive_mutex.release()

            orig.proposals_mutex.acquire()
            received_proposals = set([m.origin for m in orig.proposals])
            orig.proposals_mutex.release()

            if orig.alive_set & alive_rn == received_proposals:
                # self.queue_mutex.acquire()
                propmax = max(orig.proposals, key=lambda m: m.priority).priority
                logging.debug('Propmax: {}'.format(propmax))
                logging.debug('Selfmax: {}'.format(orig.priority))
                orig.priority = max(orig.priority, propmax)
                orig.deliverable = True
                self.msgqueue.sort(key=lambda m: m.priority)
                # self.queue_mutex.release()
                logging.debug('Marking deliverable!')
                logging.debug('Queue: {}'.format(self.msgqueue))

                # multicast msg with final priority
                final = Message(Message.FINAL, Network.get_ip(),
                                msgid=orig.msgid)
                final.priority = orig.priority
                self.queue_mutex.release()
                self.bcast_msg(final, destinations=list(received_proposals),
                               wait=False)
            else:
                self.queue_mutex.release()
                pass

        # sender has sent final priority
        elif message.msgtype == Message.FINAL:
            logging.debug('Got final')

            # get the original msg from the queue
            self.queue_mutex.acquire()
            try:
                orig = next(m for m in self.msgqueue if m.msgid == message.msgid)
            except StopIteration:
                # TODO: check this release
                self.queue_mutex.release()
                logging.warning('Bogus proposal. ID: {}'.format(message.msgid))
                return

            # TODO: check this release
            # self.queue_mutex.release()

            # update msg final priority
            # self.queue_mutex.acquire()
            logging.debug('Finalmax: {}'.format(message.priority))
            orig.priority = message.priority
            # self.queue_mutex.release()

            # update the counter
            self.counter_mutex.acquire()
            logging.debug('Counter update from {}'.format(self.counter))
            self.counter = int(max(self.counter, message.priority)) + 1
            logging.debug('Counter update to {}'.format(self.counter))
            self.counter_mutex.release()

            # mark as deliverable
            # self.queue_mutex.acquire()
            orig.deliverable = True
            self.msgqueue.sort(key=lambda m: m.priority)
            # self.queue_mutex.release()
            logging.debug('Marking deliverable!')
            logging.debug('Queue: {}'.format(self.msgqueue))

            self.queue_mutex.release()

        else:
            logging.warning('Got unknown msg type!')


    def handle_crash(self, host):
        logging.info('{} crashed at {}!'.format(host, datetime.now()))
        logging.debug('Removing crashed node from alive list')

        self.alive_mutex.acquire()
        # remove crashed node from alive list
        try:
            self.alive[host].close()
            del self.alive[host]
        except KeyError:
            logging.debug('{} has already been killed'.format(host))
            self.alive_mutex.release()
            return
        self.alive_mutex.release()

        logging.debug('Acquiring Queue mutex')
        self.queue_mutex.acquire()

        delete_idx = []
        # map of FINAL msg to a list of destinations
        final_bcast = {}

        for i, msg in enumerate(self.msgqueue):
            # msg was originally sent by the crashed node
            if msg.origin == host:
                logging.debug('Deleting msg {}'.format(msg))
                delete_idx.append(i)

            # msg was sent by me, waiting for proposal from crashed node
            elif msg.origin == Network.get_ip():
                # remove crashed node from proposals set
                logging.debug('Discarding {} from proposals list'.format(host))
                msg.proposals_mutex.acquire()
                msg.proposals.discard(host)
                received_proposals = set([m.origin for m in msg.proposals])
                msg.proposals_mutex.release()

                self.alive_mutex.acquire()
                alive_rn = set(self.alive.keys())
                self.alive_mutex.release()

                logging.debug('Checking if can be delivered...')
                # check if this can be delivered
                if msg.alive_set & alive_rn == received_proposals:
                    # self.queue_mutex.acquire()
                    propmax = max(msg.proposals, key=lambda m: m.priority).priority
                    logging.debug('Propmax: {}'.format(propmax))
                    logging.debug('Selfmax: {}'.format(msg.priority))
                    msg.priority = max(msg.priority, propmax)
                    msg.deliverable = True
                    self.msgqueue.sort(key=lambda m: m.priority)
                    # self.queue_mutex.release()

                    logging.debug('Marking deliverable with '
                                  'prio {}!'.format(msg.priority))
                    logging.debug('Queue: {}'.format(self.msgqueue))

                    # multicast msg with final priority
                    final = Message(Message.FINAL, Network.get_ip(),
                                    msgid=msg.msgid)
                    final.priority = msg.priority
                    # self.queue_mutex.release()
                    final_bcast[final] = list(received_proposals)
                    # self.queue_mutex.acquire()

        # finally delete those messages
        for idx in sorted(delete_idx, reverse=True):
            self.msgqueue.pop(idx)

        self.queue_mutex.release()

        # bcast final for those messages that have become deliverable
        # because of the crash
        for finalmsg, dest in final_bcast:
            self.bcast_msg(finalmsg, destinations=dest, wait=True)

        self.disp_func('{} is now offline...'.format(host))


    def do_delivery(self):
        while True:
            time.sleep(0.5)
            self.queue_mutex.acquire()

            msgslen = len(self.msgqueue)
            count = 0
            if msgslen > 0:
                self.msgqueue.sort(key=lambda m: m.priority)
                for msg in self.msgqueue:
                    if msg.deliverable:
                        count += 1
                        logging.debug('Delivering msg {}'.format(msg))
                        self.disp_func(msg)
                    else:
                        # break as soon as we see a non-deliverable message
                        break

                # pop as many msgs from the queue
                del self.msgqueue[:count]
            self.queue_mutex.release()


    def print_queue(self):
        self.queue_mutex.acquire()
        self.disp_func('Msg Queue: {}'.format(self.msgqueue))
        self.queue_mutex.release()


    def close(self):
        logging.info('Going offline at {}'.format(datetime.now()))
        logging.debug('Closing all sockets')
        for host in self.alive.keys():
            self.alive[host].close()


class Message:
    # msgtype can be one of "chat", "proposal", "final"
    CHAT = 'chat'
    PROPOSAL = 'proposal'
    FINAL = 'final'

    def __init__(self, msgtype, origin, msgid=None, text='', username=''):
        # raise TypeError('Message type unknown' + str(msgtype))
        self.msgtype = msgtype
        self.origin = origin
        if not msgid:
            self.msgid = uuid.uuid1()
        else:
            self.msgid = msgid
        self.text = text
        self.username = username

        self.priority = -1
        self.deliverable = False

        # set of proposals
        self.proposals = set()
        self.proposals_mutex = threading.RLock()
        # alive list at time of send
        self.alive_set = set()


    def __repr__(self):
        fmt = ('Message(type={}, origin={}, id={}, username="{}", text="{}", '
               'priority={}, deliverable={})')
        return fmt.format(
            self.msgtype, self.origin, self.msgid, self.username, self.text,
            self.priority, self.deliverable)

    def __getstate__(self):
        odict = self.__dict__.copy()
        del odict['proposals_mutex']
        return odict

    def __setstate__(self, ndict):
        self.__dict__.update(ndict)
        self.__dict__['proposals_mutex'] = threading.RLock()
