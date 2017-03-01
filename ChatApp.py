import curses
import logging
import sys
import threading

from ChatUI import ChatInterface
from Network import Network, Message

def main(stdscr):
    # get list of nodes
    nodelist = []
    with open('nodeslist.txt', 'r') as f:
        for line in f:
            line = line.split()
            addr = line[0]
            port = int(line[1])
            nodelist.append((addr, port))

    ci = ChatInterface(stdscr)

    username = ci.get_input(prompt='Enter username: ')

    ci.add_message("Welcome to ECE428 Chat App!")
    ci.add_message('Type "/quit" to exit')
    ci.add_message('Type "/online" to see who\'s online')
    ci.add_message('Type "/queue" to see message queue')

    network = Network(nodelist, ci.add_message)
    ip = Network.get_ip()

    # network.send_hello()
    ci.add_message('Connected to: ' + str(network.alive.keys()))
    ci.add_message('')

    network.start_receivers()

    while True:
        instr = ci.get_input(prompt=username + ' > ')
        if not instr:
            continue
        if instr == '/quit':
            network.close()
            logging.info('Going offline. Bye!')
            break
        if instr == '/online':
            ci.add_message('Online: ' + str(network.alive.keys()))
            continue
        if instr == '/queue':
            network.print_queue()
            continue

        message = Message(Message.CHAT, ip, text=instr, username=username)
        network.bcast_msg(message)


if __name__ == '__main__':
    if len(sys.argv) > 1:
        if sys.argv[1] == 'INFO':
            logging.basicConfig(filename='app.log', level=logging.INFO)
    else:
        logging.basicConfig(filename='app.log', level=logging.DEBUG)

    logging.info('============================')
    logging.info('==== Welcome to ChatApp ====')
    logging.info('============================')
    curses.wrapper(main)
