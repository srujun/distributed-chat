import curses
import threading

from ChatUI import ChatInterface
from Network import Network

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

    ci.add_message('Beginning connecting to other nodes, may take a while...')
    network = Network(nodelist)
    # network.send_hello()
    ci.add_message('Finished!')
    ci.add_message('')

    receiver = threading.Thread(target=recv_thread, args=(network, ci))
    receiver.daemon = True
    receiver.start()

    while True:
        instr = ci.get_input(prompt='> ')
        if instr == '/quit':
            network.close()
            break
        if instr == '/ask':
            ci.add_message('Online: ' + str(network.alive))
            continue
        ci.add_message(instr, username=username)
        network.bcast_msg(username + ': ' + instr)


def recv_thread(network, ci):
    while True:
        msgs = network.recv_msgs()
        for msg in msgs:
            if msg:
                ci.add_message(msg)


if __name__ == '__main__':
    curses.wrapper(main)
