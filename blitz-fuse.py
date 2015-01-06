#!/usr/bin/env python
import errno
import fuse
import stat
import time
import paramiko
import getpass
import socket
import os
import binascii
import sys

fuse.fuse_python_api = (0, 2)

class BlitzClient(object):
    def __init__(self, host, port):
        self.host = host
        self.port = port

        """
        self.client = paramiko.SSHClient()
        self.client.load_system_host_keys()
        self.client.set_missing_host_key_policy(paramiko.WarningPolicy())
        """

        self.sock = None
        self.chan = None
        self.transport = None

    def __del__(self):
        self.disconnect()

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))
        #self.client.connect(self.host, self.port)

    def load_key(self, keyfile):
        try:
            self.key = paramiko.RSAKey.from_private_key_file(keyfile)
        except paramiko.PasswordRequiredException:
            password = getpass.getpass('RSA key password: ')
            self.key = paramiko.RSAKey.from_private_key_file(keyfile, password)

    def get_transport(self):
        self.transport = paramiko.Transport(self.sock)
        self.transport.start_client()

    def load_keys(self):
        self.keys = paramiko.util.load_host_keys(os.path.expanduser('~/.ssh/known_hosts'))
        key = self.transport.get_remote_server_key()
        print ("KEY: %s" % binascii.hexlify(key.get_fingerprint()))

    def auth_pubkey(self, username):
        self.transport.auth_publickey(username, self.key)

    def get_channel(self):
        self.chan = self.transport.open_session()
        self.chan.get_pty()
        self.chan.invoke_shell()
        #self.chan = self.client.invoke_shell()
        #self.trasport = self.client.get_transport()
        return self.chan

    def disconnect(self):
        if self.chan is not None:
            self.chan.close()
        if self.sock is not None:
            self.sock.close()

class BlitzFuse(fuse.Fuse):
    def __init__(self, *args, **kw):
        fuse.Fuse.__init__(self, *args, **kw)

    def getattr(self, path):
        st_dir = fuse.Stat()
        st_dir.st_mode = stat.S_IFDIR | 0755
        st_dir.st_nlink = 2
        st_dir.st_atime = int(time.time())
        st_dir.st_mtime = st_dir.st_atime
        st_dir.st_ctime = st_dir.st_atime

        st_file = fuse.Stat()
        st_file.st_mode = stat.S_IFREG | 0644
        st_file.st_nlink = 1
        st_file.st_atime = int(time.time())
        st_file.st_mtime = st_file.st_atime
        st_file.st_ctime = st_file.st_atime

        if path == '/':
            return st_dir
        elif path == '/jee':
            return st_file

        return - errno.ENOENT

    def readdir(self, path, offset):
        for e in '.', '..', 'jee':
            yield fuse.Direntry(e)

def wait_for(fd, result='\n', printres=False):
    data = fd.read(1)
    res = ''
    while data != result:
        if printres:
            sys.stdout.write(data)
        res += data
        data = fd.read(1)

    return res

if __name__ == '__main__':
    cli = BlitzClient("localhost", 4444)
    cli.connect()
    cli.get_transport()
    cli.load_keys()
    cli.load_key(os.path.expanduser('~/.ssh/id_rsa'))
    cli.auth_pubkey('dummy')

    chan = cli.get_channel()

    #cli.get_channel()
    fd = chan.makefile('rU')
    wait_for(fd, '>')
    chan.send('list /libgit2\r\n')
    wait_for(fd, '\n')
    res = wait_for(fd, '>')
    print res
    #print fd.readline()
    #print fd.read(1)
    #print fd.readline()
    cli.disconnect()
    sys.exit(0)

    fs = BlitzFuse()
    fs.parse(errex=1)
    fs.main()
