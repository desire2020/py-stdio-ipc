#!/usr/bin/env python3

from io import StringIO
from queue import Queue
from threading import Thread
from subprocess import Popen, PIPE
import os
import resource
import traceback

def setrlimit():
    m = 384 * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (m, -1))

class ChildProcess():
    def __init__(self, args, stdin_save_path='/dev/null', stdout_save_path='/dev/null', stderr_save_path='/dev/null'):
        self.qmain = Queue()
        self.qthread = Queue()
        self.thread = Thread(target=self._message_thread)
        self.stdin = open(stdin_save_path, 'w')
        self.stdout = open(stdout_save_path, 'w')
        self.stderr = open(stderr_save_path, 'w')
        self.child = Popen(args, bufsize=0, stdin=PIPE, stdout=PIPE, stderr=self.stderr, universal_newlines=True, preexec_fn=setrlimit)

        self.thread.start()

    def _message_thread(self):
        try:
            while True:
                op = self.qmain.get()
                if op['command'] == 'exit':
                    break

                elif op['command'] == 'send':
                    content = op['content']
                    self.child.stdin.write(content)
                    self.child.stdin.flush()
                    self.stdin.write(content)
                    self.qthread.put('finish')

                elif op['command'] == 'recv':
                    content = ''
                    while not content.endswith('END\n'):
                        chunk = self.child.stdout.readline()
                        if not chunk:
                            break
                        content += chunk
                    content = content[:-4]
                    self.stdout.write(content)
                    self.qthread.put(content)

                else:
                    raise Exception("unsupported command")
        except Exception as e:
            traceback.print_exec()
            self.qthread.put(e)


    def send(self, content):
        self.qmain.put({ 'command': 'send', 'content': content })
        res = self.qthread.get()
        if type(res) is Exception:
            raise res

    def recv(self, timeout):
        self.qmain.put({ 'command': 'recv' })
        content = self.qthread.get(timeout=timeout)
        if type(content) is Exception:
            raise content
        return content

    def exit(self):
        self.qmain.put({ 'command': 'exit' })
        self.child.kill()
        self.thread.join()
        self.stderr.close()

