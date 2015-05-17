:mod:`findig.tools.validator` --- Request input validators
==========================================================

.. automodule:: findig.tools.validator
    :members:
    :exclude-members: ValidationFailed, InvalidSpecificationError

    .. autoexception:: ValidationFailed()

        .. attribute:: fields
            
            A list of field names for which validation has failed. This will
            always be a complete list of failed fields.

        .. attribute:: validator

            The :class:`Validator` that raised the exception.