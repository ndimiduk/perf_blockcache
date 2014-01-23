# Python setup

This test harness uses the python library Fabric to drive operations and Pandas
to compute summary statistics over the logged data. These are instructions for
setting up the python environment.

## install environment

From CentOS, use your package manager. On a Mac, I've had good luck
using [Homebrew][0].

    $ yum install python

or

    $ brew install python

I use `pip` to install dependencies, and `virtualenv` to create a sandbox jail
for the installation. If your package manager provides packages for either of
these, it's probably best to use that. Otherwise:

    $ wget https://raw.github.com/pypa/pip/master/contrib/get-pip.py
    $ python get-pip.py
    $ pip install virtualenv

Also, you'll need the standard development kit in order to compile C modules
for some of the python libraries and dependencies.

    $ yum groupinstall 'Development Tools'

On a Mac, you had to install these as a dependency for Homebrew.

That's all you need to install into the root (/) of the base system. Everything
else is put into a local "jail".

## create jail, install dependencies

Create your virtualenv. I call mine "fab," short for Fabric.

    $ virtualenv /path/to/fab
    $ /path/to/fab/bin/pip install fabric
    $ /path/to/fab/bin/pip install pandas

Confirm installation of Fabric.

    $ /path/to/fab/bin/fab --help
    Usage: fab [options] <command>[:arg1,arg2=val2,host=foo,hosts='h1;h2',...] ...
    ...

And Pandas.

    $ /path/to/fab/bin/pyhton -c "import pandas ; print pandas.DataFrame([[1,2,3],[4,5,6]])"
       0  1  2
    0  1  2  3
    1  4  5  6
    
    [2 rows x 3 columns]


[0]: http://brew.sh/
