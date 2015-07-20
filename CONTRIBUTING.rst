Contributing to Findig
======================

Your contributions to this project are welcome! Here are a few guidelines to
help you get the most out of contributing.

Support
-------

If you're having issues using Findig that aren't related to a bug, then you
want to be using the `Gitter Chat`_. It's free of charge, but you'll need a
GitHub account to use it.

.. _gitter chat: https://gitter.im/geniphi/findig

Bug Reports
-----------

The official issue tracker for Findig resides at 
https://github.com/geniphi/findig/issues. Use it if what you're reporting is
a bug.

The issue tracker can also be used for feature requests and reporting 
documentation errors.

Patches
-------

Please use the GitHub pull requests feature to submit patches. Before doing so,
try [#f1]_ to ensure that you've followed the following guidelines:

* If you're submitting new code, please write some unit tests for it. Findig
  using `PyTest`_ for test discovery and the tests go in the top-level tests/
  folder. If your code fixes a bug, make sure that the tests you add fail
  without your code.

* If your patch implements a new feature, you should (in general) have created 
  an issue an issue on the issue tracker and discussed its design and 
  implementation.

* New code should try to follow the :pep:`PEP8 <8>` style guide.

.. [#f1] Within reason.

.. _pytest: http://pytest.org/

Running tests
~~~~~~~~~~~~~

Findig uses PyTest for its unit tests. You can run them like so::

    $ py.test tests/ --doctest-modules findig

Or, use `Tox`_ to run all of checks available::

    $ tox

.. _tox: http://tox.testrun.org/
