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
import uuid

fuse.fuse_python_api = (0, 2)

class BlitzClient(object):
    def __init__(self, host, port):
        self.host = host
        self.port = port

        self.sock = None
        self.chan = None
        self.fd = None
        self.transport = None

        self.keys = None
        self.key = None

    def __del__(self):
        self.disconnect()

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))

    def load_key(self, keyfile):
        if self.key is not None:
            return
        try:
            self.key = paramiko.RSAKey.from_private_key_file(keyfile)
        except paramiko.PasswordRequiredException:
            password = getpass.getpass('RSA key password: ')
            self.key = paramiko.RSAKey.from_private_key_file(keyfile, password)

    def get_transport(self):
        self.transport = paramiko.Transport(self.sock)
        self.transport.start_client()

    def load_keys(self):
        # if self.keys is None:
        #    self.keys = paramiko.util.load_host_keys(os.path.expanduser('~/.ssh/known_hosts'))
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

    def close(self):
        if self.fd is not None:
            self.fd.close()
            self.fd = None
        if self.chan is not None:
            self.chan.close()
            self.chan = None

    def disconnect(self):
        if self.fd is not None:
            self.fd.close()
            self.fd = None
        if self.chan is not None:
            self.chan.close()
            self.chan = None
        if self.transport is not None:
            self.transport.close()
            self.transport = None
        if self.sock is not None:
            self.sock.close()
            self.sock = None

    def wait_for(self, result='\n', printres=False):
        data = self.fd.read(1)
        if not data:
            return ''
        buf = data
        res = ''
        rsize = len(result)
        while buf != result:
            if printres:
                sys.stdout.write(data)
            data = self.fd.read(1)
            if not data:
                return res
            res += data
            buf += data
            if len(buf) > rsize:
                buf = buf[-rsize:]

        return res

    def list(self, folder):
        self.chan.send('list %s\r\n' % (folder))
        self.wait_for('OK')
        self.wait_for('\n')
        res = self.wait_for('>')
        if res and res[-1] == '>':
            res = res[:-1]
        if res.startswith('ERROR'):
            raise ValueError(res.strip())
        return [x.strip() for x in res.split('\n') if x.strip()]

    def get(self, filename):
        self.chan.send('get %s\r\n' % (filename.strip()))
        self.wait_for('OK')
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

    def stat(self, filename):
        self.chan.send('stat %s\r\n' % (filename))
        self.wait_for('OK')
        self.wait_for('\n')

        res = self.fd.readline()
        self.wait_for('>')

        res = res.strip()
        if res.startswith('ERROR'):
            raise ValueError('ERROR: %s' % res)

        entries = res.split(' ')
        if len(entries) < 2:
            raise ValueError('ERROR: Num entries %s' % (res))

        ftype = entries[0]
        size = entries[1]
        if not size.isdigit():
            raise ValueError('ERROR: size (%s, %s)' % (size, res))

        size = int(size)
        name = ' '.join(entries[2:])

        return (ftype, size, name)

class BlitzFuse(fuse.Operations):
    def __init__(self, *args, **kw):
        self.msgfile = '/tmp/blitz_'+ str(uuid.uuid4())

        self.host = 'localhost'
        self.port = 4444

        self.cli = BlitzClient(self.host, self.port)
        self.cli.connect()
        self.cli.get_transport()
        self.cli.load_keys()
        self.cli.load_key(os.path.expanduser('~/.ssh/id_rsa'))
        self.cli.auth_pubkey('dummy')

        self.chan = None
        self.channel()
        #fuse.Fuse.__init__(self, *args, **kw)

    def channel(self):
        self.chan = self.cli.get_channel()

        self.wait_prompt()

    def connect(self):
        #self.cli.connect()
        return

    def disconnect(self):
        return
        #self.cli.disconnect()
        self.cli.close()
        #self.cli = None
        self.chan = None

    def wait_prompt(self):
        self.cli.wait_for('>')

    def getattr(self, path, fh=None):
        res = {
            'st_atime': int(time.time()),
            'st_nlink': 1,
            'st_size': 0
        }
        res['st_mtime'] = res['st_atime']
        res['st_ctime'] = res['st_atime']

        if path == '/' or path == '.' or path == '..':
            ftype = 'DIR'
            fsize = 36
        else:
            try:
                self.connect()
                (ftype, fsize, fname) = self.cli.stat(path)
                self.disconnect()
            except Exception as e:
                self.log_to_file(e)
                raise fuse.FuseOSError(errno.ENOENT)

        if ftype == 'DIR':
            res['st_mode'] = stat.S_IFDIR | 0755
            res['st_size'] = fsize
        elif ftype == 'FILE':
            res['st_mode'] = stat.S_IFREG | 0644
            res['st_size'] = fsize
        else:
            raise fuse.FuseOSError(errno.ENOENT)

        return res

    def readdir(self, path, offset):
        try:
            res = ['.', '..']
            try:
                self.connect()
                res += self.cli.list(path)
                self.disconnect()
            except Exception as e:
                self.log_to_file(e)

            for ent in res:
                yield os.path.basename(ent)
        except:
            return

    def open(self, path, flags):
        full_path = self._full_path(path)
        return os.open(full_path, flags)

    def log_to_file(self, msg):
        with open(self.msgfile, 'a') as fd:
            fd.write('%s\n' % msg)

if __name__ == '__main__':
    fuse.FUSE(BlitzFuse(), sys.argv[1], foreground=True)
