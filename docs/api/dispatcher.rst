:mod:`findig.dispatcher` -- Low-level dispatchers for Findig applications
=========================================================================

.. automodule:: findig.dispatcher

    This low-level module defines the :class:`Dispatcher` class,
    from which :class:`findig.App` derives.

    .. autoclass:: findig.dispatcher.Dispatcher
        :members:

        .. attribute:: formatter

            If a *formatter* function was given to the
            constructor, then that is used. Otherwise, a generic
            :class:`findig.content.Formatter` is used.

        .. attribute:: parser
            
            The value that was passed for *parser* to the constructor.
            If no argument for *parser* was given to the constructor, then
            a generic :class:`findig.content.Parser` is used.

        .. attribute:: error_handler

            The value that was passed for error_handler to the constructor,
            or if None was given, then a generic
            :class:`findig.content.ErrorHandler`.