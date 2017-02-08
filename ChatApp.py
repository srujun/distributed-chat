import curses
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
    ci.add_message('')

    network = Network(nodelist)
    network.send_hello()

    while True:
        instr = ci.get_input(prompt='> ')
        if instr == '/quit':
            network.close()
            break
        ci.add_message(instr, username=username)


if __name__ == '__main__':
    curses.wrapper(main)
