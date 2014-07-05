Installation
============

.. note:: Findig is pre-release software and isn't currently installable
          by PyPI. Currently though only way to install Findig is using
          its development version.

Installing Findig is easy, as long as you have the right tool for the
job. Make sure you have `pip installed`_ before proceeding.

.. _`pip installed`: http://pip.readthedocs.org/en/latest/installing.html

Supported Python versions
-------------------------

Findig currently supports Python 2.7.

Installing the development version
----------------------------------

You can install the development version of Findig straight from 
Github_. Just run the following pip command (make sure you 
have git installed on your system)::

    $ pip install git+https://github.com/geniphi/findig/findig.git#egg=Findig

This will install the latest version of Findig on your system.

Getting extra features
----------------------

Findig has some extra features that are enabled when certain packages
are installed on the system. They are defined as extras that can be 
specified when installing Findig. To install an extra feature, just
include its name inside square brackets immediately after 'Findig' in
your pip install command. Multiple extra features can be installed by 
listing them inside square brackets, separated by commas. For example, to 
install the development version of Findig with redis cache support, run 
this command::

    $ pip install git+https://github.com/geniphi/findig/findig.git#egg=Findig[redis]

And pip will install Findig along with all the requirements necessary
for the extra feature to work.

Here's a list of all the supported extra features:

============ ========================= ======================
Feature name Description               Installed Requirements
============ ========================= ======================
redis        Redis cache support       redis
jinja        Jinja2 templating support jinja2
============ ========================= ======================

Getting the source code
-----------------------

The source code for Findig is hosted on Github_. If you have Git
installed, you can clone the repository straight to your hard drive
from a command shell::

    $ git clone git://github.com/geniphi/findig/findig.git

Alternatively, you can download a source tarball_ or zipball_, both of 
which will contain the latest source code from the repository.

.. _zipball: https://github.com/geniphi/findig/zipball/master
.. _tarball: https://github.com/geniphi/findig/tarball/master
.. _github: https://github.com/geniphi/findig
