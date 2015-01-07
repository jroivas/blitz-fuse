# Blitz-fuse

Mount [blitz-repos](https://github.com/jroivas/blitz-repos) over FUSE.
Needs blitz-repos servers running and serving via SSH.
Connects to it and provides read-only file access to files and directories.


## Install

Use virtualenv after installing libfuse-dev:

    sudo apt-get install libfuse-dev

    virtualenv --system-site-packages env
    env/bin/pip install fusepy


## Usage

Simply tell mountpoint to use defaults:

    mkdir mountpoint
    blitz-fuse mountpoint

You can have more fine grained control over it:

    blitz-fuse --server localhost --port 4444 --cache --logfile my_fuse.log mountpoint
