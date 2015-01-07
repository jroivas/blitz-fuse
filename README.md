# Blitz-fuse

Mount [blitz-repos](https://github.com/jroivas/blitz-repos) over FUSE.
Needs blitz-repos servers running and serving via SSH.
Connects to it and provides read-only file access to files and directories.


## Install

Use virtualenv after installing libfuse-dev:

    sudo apt-get install libfuse-dev
    sudo apt-get install python-paramiko

    virtualenv --system-site-packages env
    env/bin/pip install fusepy
    env/bin/pip install paramiko


## Usage

First put blitz-repo serving files.
Then simply tell mountpoint to use defaults:

    mkdir mountpoint
    env/bin/python blitz-fuse.py mountpoint

You can have more fine grained control over it:

    env/bin/python blitz-fuse.py --server localhost --port 4444 --cache --logfile my_fuse.log mountpoint
