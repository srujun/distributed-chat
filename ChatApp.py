import curses
from ChatUI import ChatInterface

def main(stdscr):
    ci = ChatInterface(stdscr)

    username = ci.get_input(prompt='Enter username: ')

    ci.add_message("Welcome to ECE428 Chat App!")
    ci.add_message('Type "/quit" to exit')
    ci.add_message('')

    while True:
        instr = ci.get_input(prompt='> ')
        if instr == '/quit':
            break
        ci.add_message(instr, username=username)


if __name__ == '__main__':
    curses.wrapper(main)
