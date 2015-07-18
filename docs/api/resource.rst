:mod:`findig.resource` --- Classes for representing API resources
=================================================================

.. automodule:: findig.resource
    :members:
    :show-inheritance:
    :exclude-members: Resource

    .. autoclass:: Resource
        :members:
        :show-inheritance:

        .. attribute:: model

            The value that was passed for *model* to the constructor, or
            if None was given, a :class:`~findig.data_model.DataModel`.

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