Findig
======

|build-status| |docs| |license| |gitter-chat|

Findig is a micro-framework for building HTTP applications. It is based
on the excellent Werkzeug_ WSGI utility library, and is meant as an
alternative to Flask_ when implementing RESTful APIs.

.. _werkzeug: http://werkzeug.pocoo.org
.. _flask: http://flask.pocoo.org

Features
--------

- Declarative support for RESTful API development.
- Fully customizable input and output content-types.
- High level utilities.

Installing
----------

Findig is pre-release software and is not yet published on PyPI. To
install the development version, run:

.. code-block:: bash

    $ pip install git+https://github.com/geniphi/findig.git#egg=Findig
    
Findig is written in Python3 and is supported on Python 3.4.

Contribute
----------

- Issue Tracker: http://github.com/geniphi/findig/issues
- Source Code: http://github.com/geniphi/findig

Support
-------

If you're having issues using Findig, please use the issue tracker to let 
us know about them.

License
-------

This project is licensed under the MIT License.

Documentation
-------------

This project is documented at 
`findig@readthedocs <http://findig.rtfd.org/>`_.

.. |docs| image:: https://readthedocs.org/projects/findig/badge/?version=latest
    :alt: Documentation Status
    :scale: 100%
    :target: https://readthedocs.org/projects/findig/
    
.. |build-status| image:: https://travis-ci.org/geniphi/findig.svg?branch=develop
    :target: https://travis-ci.org/geniphi/findig
    :alt: build status
    :scale: 100%
    
.. |license| image:: https://img.shields.io/badge/license-MIT-blue.svg
    :target: https://raw.githubusercontent.com/geniphi/findig/develop/LICENSE.txt
    :alt: License
    :scale: 100%

.. |gitter-chat| image:: https://img.shields.io/badge/gitter-support-brightgreen.svg
    :target: https://gitter.im/geniphi/findig
    :alt: Gitter support
    :scale: 100%
