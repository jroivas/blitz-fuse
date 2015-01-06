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
        self.fd = self.chan.makefile('rU')
        return self.chan

    def disconnect(self):
        if self.chan is not None:
            self.chan.close()
        if self.sock is not None:
            self.sock.close()

    def wait_for(self, result='\n', printres=False):
        data = self.fd.read(1)
        res = ''
        while data != result:
            if printres:
                sys.stdout.write(data)
            res += data
            data = self.fd.read(1)

        return res

    def list(self, folder):
        chan.send('list %s\r\n' % (folder))
        self.wait_for('\n')
        res = self.wait_for('>')
        if res.startswith('ERROR'):
            raise ValueError(res.strip())
        return [x.strip() for x in res.split('\n') if x.strip()]

    def get(self, filename):
        chan.send('get %s\r\n' % (filename))
        self.wait_for('\n')

        name = self.fd.readline()
        if name.startswith('ERROR') or not name.startswith('File:'):
            raise ValueError(name.strip())
        size = self.fd.readline()
        if not size.startswith('Size:'):
            raise ValueError(size.strip())
        name = name[5:].strip()
        size = size[5:].strip()
        if not size.isdigit():
            raise ValueError(size)
        size = int(size)
        data = self.fd.read(size)
        self.wait_for('>')
        return (name, size, data)

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

if __name__ == '__main__':
    cli = BlitzClient("localhost", 4444)
    cli.connect()
    cli.get_transport()
    cli.load_keys()
    cli.load_key(os.path.expanduser('~/.ssh/id_rsa'))
    cli.auth_pubkey('dummy')

    chan = cli.get_channel()

    cli.wait_for('>')
    #print cli.list('/libgit2')
    name, size, data = cli.get('/libgit2/AUTHORS')
    with open('authors.inp', 'w+') as fd:
        fd.write(data)
    #print data

    cli.disconnect()
    sys.exit(0)

    fs = BlitzFuse()
    fs.parse(errex=1)
    fs.main()
