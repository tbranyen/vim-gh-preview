import os
import signal
import time
import Queue
import httplib
import threading
import subprocess
import json
import vim
import sys
import socket


ghp_process = None
ghp_t = None
ghp_t_stop = None
ghp_started = False
ghp_queue = Queue.Queue(1)


def terminate_process(pid):
    if sys.platform == 'win32':
        import ctypes
        PROCESS_TERMINATE = 1
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
        ctypes.windll.kernel32.TerminateProcess(handle, -1)
        ctypes.windll.kernel32.CloseHandle(handle)
    else:
        os.kill(pid, signal.SIGKILL)


def start_browser(url):
    print(url)
    command =\
         'open -g'  if sys.platform.startswith('darwin')\
    else 'start'    if sys.platform.startswith('win')\
    else 'xdg-open'
    os.system(command + ' ' + url)


def push(stop_event, port, auto_open_browser, auto_start_server):
    global ghp_process
    process_failed = False
    browser_opened = False
    while(not stop_event.is_set()):
        success = False
        data = ghp_queue.get()

        connection = httplib.HTTPConnection('localhost', port, timeout=1)
        try:
            connection.request(
                'POST',
                '/api/doc/',
                data,
                { 'Content-Type': 'application/json' })
            connection.close()
            success = True
        except (socket.error, socket.timeout, httplib.HTTPException):
            if not ghp_process \
               and not process_failed \
               and auto_start_server:
                startupinfo = None
                if sys.platform == 'win32':
                    command = "gh-preview.cmd"
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    pipe = None
                else:
                    command = "gh-preview"
                    pipe = subprocess.PIPE
                try:
                    ghp_process = subprocess.Popen(
                        [command, port]
                      , bufsize = 0
                      , startupinfo = startupinfo
                      , stdin = pipe
                      , stdout = pipe
                      , stderr = pipe
                    )
                    success = True
                except Exception, e:
                    process_failed = True
        except Exception, e:
            print(type(e))

        if success and not browser_opened:
            browser_opened = True
            start_browser('http://localhost:' + port)

        ghp_queue.task_done()
    if ghp_process is not None:
        terminate_process(ghp_process.pid)

def preview():
    global ghp_queue

    # Calculate the line
    scroll_offset = 10
    lines = len(vim.current.buffer)
    (line, _) = vim.current.window.cursor
    first_line = int(vim.eval('line("w0")'))
    last_line = int(vim.eval('line("w$")'))
    if (last_line - first_line) > scroll_offset:
        if (line - first_line) < scroll_offset and \
           (first_line > scroll_offset):
            line = first_line + scroll_offset
        elif (last_line - line) < scroll_offset and \
             (last_line < lines - scroll_offset):
            line = last_line - scroll_offset

    try:
        ghp_queue.put(
            json.dumps({
                'file': vim.current.buffer.name
              , 'markdown': '\n'.join(vim.current.buffer).decode('utf-8')
              , 'cursor': line
              , 'lines': lines
            })
          , block = False
        )
    except:
        pass

def stop():

    global ghp_t
    global ghp_t_stop
    global ghp_started
    global ghp_process

    if not ghp_started:
        return
    ghp_started = False

    ghp_t_stop.set()
    ghp_t._Thread__stop()

    if ghp_process is not None:
        terminate_process(ghp_process.pid)

def start():

    global ghp_t
    global ghp_t_stop
    global ghp_started
    global ghp_process

    if ghp_started:
        return
    ghp_started = True

    ghp_t_stop = threading.Event()
    ghp_t = threading.Thread(target=push, args=(
        ghp_t_stop
      , vim.eval("g:ghp_port")
      , vim.eval("g:ghp_open_browser")
      , vim.eval("g:ghp_start_server")
    ))
    ghp_t.start()