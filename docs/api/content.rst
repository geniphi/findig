findig.content: formatters, parsers and error handlers
======================================================

.. automodule:: findig.content

    .. autoclass:: ErrorHandler
        
        .. automethod:: register(err_type, handler)


    .. autoclass:: Formatter

        .. automethod:: register(mime_type, handler, default=False)


    .. autoclass:: Parser

        .. automethod:: register(mime_type, handler, default=False)