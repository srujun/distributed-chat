import curses
import logging

from Network import Message

class ChatInterface:
    def __init__(self, stdscr, chatbox_lines=2):
        stdscr.clear()
        stdscr.scrollok(True)
        curses.use_default_colors()

        # nlines, ncols, begin_y, begin_x
        win_messages_props = [curses.LINES - chatbox_lines, curses.COLS, 0, 0]
        win_chatbox_props = [chatbox_lines, curses.COLS,
                             curses.LINES - chatbox_lines, 0]

        self.win_messages = stdscr.derwin(*win_messages_props)
        self.win_messages.scrollok(True)
        self.win_chatbox = stdscr.derwin(*win_chatbox_props)
        self.stdscr = stdscr

        self.chatbuffer = []

        self.stdscr.refresh()

    def redraw_chatbox(self):
        self.win_chatbox.clear()
        message = ''.join(self.chatbuffer)
        self.win_chatbox.addstr(0, 0, message)
        self.win_chatbox.refresh()

    def get_input(self, prompt=''):
        del self.chatbuffer[:]
        self.chatbuffer.append(prompt)
        self.redraw_chatbox()

        while True:
            inch = self.win_chatbox.getch()
            xpos = self.win_chatbox.getyx()[1]

            if inch == curses.KEY_BACKSPACE or inch == 127:
                if len(self.chatbuffer) - 1 > 0:
                    self.chatbuffer.pop()
            elif inch == ord('\n'):
                message = ''.join(self.chatbuffer[1:])
                del self.chatbuffer[:]
                self.redraw_chatbox()
                return message
            elif xpos >= self.win_chatbox.getmaxyx()[1] - 2:
                continue
            elif 32 <= inch <= 255:
                self.chatbuffer.append(chr(inch))

            self.redraw_chatbox()

    def add_message(self, message, username=''):
        if type(message) is str:
            if not message.endswith('\n'):
                message = message + '\n'

            if username:
                self.win_messages.addstr('{')
                self.win_messages.addstr(username, curses.color_pair(1))
                self.win_messages.addstr('}: ')
            self.win_messages.addstr(message)
            self.win_messages.refresh()

        elif isinstance(message, Message) and message.msgtype == Message.CHAT:
            msgtext = ''

            if not message.text.endswith('\n'):
                msgtext = message.text + '\n'
            else:
                msgtext = message.text

            if message.username:
                self.win_messages.addstr('{')
                self.win_messages.addstr(message.username, curses.color_pair(1))
                self.win_messages.addstr('}: ')
            else if username:
                self.win_messages.addstr('{')
                self.win_messages.addstr(username, curses.color_pair(1))
                self.win_messages.addstr('}: ')

            self.win_messages.addstr(msgtext)
            self.win_messages.refresh()

        else:
            logging.error('Msg is broken: ' + str(message))
