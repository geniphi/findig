:mod:`findig.tools.protector` --- Authorization tools
=====================================================

.. automodule:: findig.tools.protector

    For many web API resources, it is desirable to restrict access to only
    specific users or clients that have been authorized to use them. The tools in
    this module provide one mechanism for putting such restrictions in place.

    The :class:`Protector` is the core tool provided here. Its instances collect
    information about resources that should be guarded against authorized access,
    and on each request, it checks that requests to those resources present a valid 
    authorization.

    The precise authorization mechanism used by the protector is controlled by
    the :class:`GateKeeper` abstract class for which an application developer may
    supply their own concrete instance. Alternatively, some protectors
    supply their own gatekeepers (example: :class:`BasicProtector`
    uses :rfc:`2617#section-2` as its authorization mechanism).

    .. _auth-scopes:

    Scopes
    -------------------

    Protectors provide implicit support for 'scopes' (an idea 
    borrowed from OAuth 2, with some enhancements). While completely optional,
    their use provides a way allow access to only portions of an API while
    denying access to others.

    An authorization (commonly represented by a token) may have some scopes
    (identified by application chosen strings)
    associated with it which define what portions of the API that a request
    using the authorization can access; only resources belong to one of the
    scopes associated with the authorization, or resources that belong to
    no scopes are accessible. Protectors provide a mechanism for marking a 
    guarded resource as belonging to a scope.

    For example, an application may provide a resource guarded under the scope 
    ``foobar``. In order to access the resource, then a request must present
    authorization that encapsulates the ``foobar`` scope, otherwise the request
    is denied.

    .. tip:: While recommended, using scopes is optional. In fact, some 
             authorization mechanisms do not provide a way to encapsulate
             scopes. To provide scope support for a custom authentication
             mechanism that encapsulates scopes, see :class:`GateKeeper`.

    Findig extends authorization scopes with special semantics that can affect
    the way they are used by a protector. The grammar for authorization scopes
    is given below:

    .. productionlist:: Authorization scope
        auth_scope : scope_name["+"permissions]
        scope_name : scope_fragment{"/"scope_fragment}
        permissions : permission{permission}
        permission : "c" | "r" | "u" | "d"

    ``scope_fragment`` is token that does not include the '+' or '/' characters.
    Whenever a permission is omitted, the 'r' is permission is implied.

    Permissions are used to control which actions an authorization permits on
    the resources falling into its scope, according to this table:

    ======      ===============
    Action      Permission
    ======      ===============
    HEAD        ``r``
    ------      ---------------
    GET         ``r``
    ------      ---------------
    POST        ``c``
    ------      ---------------
    PUT         ``c`` and ``u``
    ------      ---------------
    DELETE      ``d``
    ======      ===============

    So for example, an authorization with the scope ``foobar+rd`` can read
    and delete resources under the ``foobar`` scope.

    The '/' character is used to denote sub-scopes (and super-scopes). ``foo/bar``
    is considered a sub-scope of ``foo`` (and ``foo`` a super-scope of 
    ``foo/bar``), and so on. This is useful, because by default if a request
    possesses authorization for a super-scope, then this implicitly authorizes
    its sub-scopes as well.

    Scopes attached to a resource follow a simpler grammar:

    .. productionlist::
        resource_scope : `scope_name`

    In other words, the permissions are omitted (because the protector multiplexes
    which permission is required from the request method).

    The :mod:`findig.tools.protector.scopeutil` module provides some functions
    for working with scopes.

    Protectors
    ----------

    .. autoclass:: Protector
        :members:

    .. autoclass:: BasicProtector
        :members:

    GateKeepers
    -----------

    Each :class:`Protector` should be supplied with a :class:`GateKeeper`
    that extracts any authorization information embedded in
    a request. :class:`Protector` uses a default gatekeeper which denies all
    requests made to its guarded resources. 

    An application may provide its own gatekeeper that implements the
    desired authorization mechanism. That's done by implementing the
    :class:`GateKeeper` abstract base class.

    .. autoclass:: GateKeeper
        :members:
