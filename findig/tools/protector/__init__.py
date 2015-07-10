from abc import ABCMeta, abstractmethod
from collections.abc import Callable
from functools import partial

from werkzeug.exceptions import Forbidden, Unauthorized

from . import scopeutil
from findig.context import ctx
from findig.dispatcher import AbstractResource


class GateKeeper(metaclass=ABCMeta):
    """
    To implement a gatekeeper, implement at least :meth:`check_auth` and
    :meth:`get_username`.
    """
    @abstractmethod
    def check_auth(self):
        """
        Try to perform an authorization check using the request context variables.

        Perform the authorization check using whatever mechanism that the
        gatekeeper's authorization is handled. If authorization fails, then
        an :class:`~werkzeug.exceptions.Unauthorized` error should be raised.

        Return a 'grant' that will be used to query the gatekeeper about the
        authorization.

        """

    @abstractmethod
    def get_username(self, grant):
        """Return the username/id of the user that authorized the grant."""

    def get_scopes(self, grant):
        """Return a list of scopes that the grant is authorized with. (Optional)"""
        # By default the gatekeeper will not consider scopes
        return [scopeutil.ANY]

    def get_clientid(self, grant):
        """Return the client that sent the request to the grant. (Optional)"""
        # By default the gatekeeper doesn't grant scope
        return None


class DefaultGateKeeper(GateKeeper):
    """
    A concrete :class:`GateKeeper` that does not perform any authorizations.

    When used with a protector, this gatekeeper will result in all guarded resources being
    blocked. It's intended to be replaced with a different implementation of the
    GateKeeper class.
    """
    def check_auth(self):
        import warnings
        warnings.warn("The protector guarding this resource is using the "
                      "default gate keeper, which denies all requests to this "
                      "resource. If a different behavior is desired (likely), "
                      "please configure the protector with a different gatekeeper.")
        raise Unauthorized

    def get_username(self, grant):
        raise NotImplementedError


class Protector:
    """
    A protector is responsible for guarding access to a restricted
    resource.

    >>> protector = Protector()
    >>> protector.guard(resource, "user", "friend")

    """

    _default_permissions = {"get": "r", "post": "c", "patch": "cu", "delete": "d", "head": "r"}

    def __init__(self, app=None, subscope_separator="/", gatekeeper=DefaultGateKeeper()):
        self._subsep = subscope_separator
        self._gatekeeper = gatekeeper
        self._guard_specs = {}

        if app is not None:
            self.attach_to(app)

    def attach_to(self, app):
        """
        Attach the protector to a findig application.

        .. note:: This is called automatically for any app that is passed
            to the protector's constructor.

        By attaching the protector to a findig application, the protector is
        enabled to intercept requests made to the application, performing authorization
        checks as needed.

        :param app: A findig application whose requests the protector will 
            intercept.
        :type app: :class:`findig.App`, or a subclass like 
            :class:`findig.json.App`.

        """
        app.context(self.auth)

    def guard(self, *args):
        """
        guard(resource, *scopes)

        Guard a resource against unauthorized access. If given, the scopes
        will be used to protect the resource (similar to oauth) such that
        only requests with the appropriate scope will be allowed through.

        If this function is called more than once, then a grant by *any*
        of the specifications will allow the request to access the resource.
        For example::

            # This protector will allow requests to res with both 
            # "user" and "friends" scope, but it will also allow 
            # requests with only "foo" scope.
            protector.guard(res, "user", "friends")
            protector.guard(res, "foo")

        A protector can also be used to decorate resources for guarding::

            @protector.guard
            @app.route("/foo"):
                # This resource is guarded with no scopes; any authenticated
                # request will be allowed through.
                pass

            @protector.guard("user/email_addresses")
            @app.route("/bar"):
                # This resource is guarded with "user/email_addresses" scope,
                # so that only requests authorized with that scope will be
                # allowed to access the resource.

            @protector.guard("user/phone_numbers", "user/contact")
            @app.route("/baz"):
                # This resource is guarded with both "user/phone_numbers" and
                # "user/contact" scope, so requests must be authorized with both
                # to access this resource.

            # NOTE: Depending on the value passed for 'subscope_separator' to the
            # protector's constructor, authenticated requests authorized with "user" scope
            # will also be allowed to access all of these resources (default behavior).

        """
        def add_resource(resource, scopes=None):
            self._guard_specs.setdefault(resource.name, []).append(
                [] if scopes is None else list(scopes)
            )
            return resource

        if len(args) == 0:
            return add_resource

        elif isinstance(args[0], AbstractResource):
            return add_resource(args[0], args[1:])

        else:
            return partial(add_resource, scopes=args)

    def auth(self):
        resource = ctx.resource
        auth_info = {}

        # Check if the request is guarded
        if resource.name in self._guard_specs:
            grant = self._gatekeeper.check_auth()
            scopes = auth_info['scopes'] = self._gatekeeper.get_scopes(grant)
            auth_info['user'] = self._gatekeeper.get_username(grant)
            auth_info['client'] = self._gatekeeper.get_clientid(grant)

            permissions = self._default_permissions.get(request.method.lower(), "crud")
            
            # Try to find a guard who will let the request through
            for scope_guard in self._guard_specs[resource.name]:
                for scope in scope_guard:
                    # Affix the request permissions to the required scope
                    scope = "{}+{}".format(scope, permissions)

                    if not scopeutil.find_granting_scope(scope, scopes, self._subsep):
                        # This guard is looking for a scope that the request
                        # can't satisfy, so give up on the guard.
                        break
                else:
                    # The request satisfies all the scopes that the guard is looking
                    # for, so stop looking.
                    break
            else:
                # Unable to find a guard that will let the request through with the
                # given scope, so raise an error.
                raise InsufficientScope(self._guard_specs[resource.name])
            
        # Yielding this value will place it on the request context with the same name
        # as this function: 'findig.context.ctx.auth'.
        yield auth_info

    @property
    def authenticated_user(self):
        """Get the username/id of the authenticated user for the current request."""
        return ctx.auth['user']

    @property
    def authenticated_client(self):
        """Get the client id of the authenticated client for the current request, or None."""
        return ctx.auth['client']

    @property
    def authorized_scope(self):
        """Get the a list of authorized scopes for the current request."""
        return ctx.auth['scopes']


class BasicProtector(GateKeeper, Protector):
    """
    A :class:`Protector` that implements HTTP Basic Auth.

    While straightforward, this protector has a few security considerations:

    * Credentials are transmitted in plain-text. If you must use this
      protector, then at the very least the HTTPS protocol should be
      used.

    * Credentials are transmitted with *each request*. It requires that clients
      either store user credentials, or prompt the user for their credentials at
      frequent intervals (possibly every request).

    * This protector offers no scoping support; a grant from this protector 
      allows unlimited access to any resource that it guards.

    """
    def __init__(self, app=None, subscope_separator="/", auth_func=None, realm="guarded"):
        super().__init__(app=app, subscope_separator=subscope_separator, gatekeeper=self)
        self._fauth = auth_func
        self._realm = realm

    def auth_func(self, fauth):
        self._fauth = fauth
        return fauth

    def check_auth(self):
        request = ctx.request
        resource = ctx.resource
        auth = request.authorization

        if self._fauth is None:
            import warnings
            warnings.warn("The HTTP basic auth protector doesn't know how to validate "
                          "credentials. Please supply it with an auth_func parameter. "
                          "See the documentation for "
                          "findig.tools.protector.BasicProtector.auth_func.")

        if auth and self._fauth(auth.username, auth.password):
            return auth.username

        else:
            realm = self._realm(resource) if isinstance(self._realm, Callable) else self._realm
            response = Unauthorized().get_response(request)
            response.headers["WWW-Authenticate"] = "Basic realm=\"{}\"".format(realm)
            raise Unauthorized(response=response)

    def get_username(self, grant:"This is the username"):
        return grant


class InsufficientScope(Forbidden):
    pass
