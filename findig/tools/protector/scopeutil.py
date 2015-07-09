"""
These are utility functions that help to implement scopes on a protected API.
"""

import re


ANY = {"*+crud"}

def normalize_scope_items(scopes, default_mode="r", raise_err=True):
    """
    Return a set of scope items that have been normalized.

    A normalized set of scope items is one where every item
    is in the format::

        item_name+permission

    where permission can be any one of 'c', 'r', 'u' or 'd'.

    Input scope items are assumed to be 'r' by default. Example,
    the scope item 'user' will normalize to 'user+r'.

    Input scope items that contain more than one permission are
    expanded to multiple scope items. For example the scope item
    "user+ud" is expanded to ("user+u", "user+d").

    Malformed scope items are dropped. For example, the scope item
    "user+r+u" is removed.

    Note that permissions are atomic, and none implies another.
    For example, "user+u" will expand to "user+u" and NOT
    ("user+r", "user+u").
    """

    normalized = set()
    rep = re.compile(r'^(?P<item>(?:[^\W\d_]|[!#-*,-\[\]-~])+)(?:\+(?P<permissions>[crud]+))?$', re.U)

    for item in scopes:
        match = rep.fullmatch(item)
        if match is not None:
            item = match.group("item")
            permissions = match.group("permissions") or default_mode

            for p in permissions:
                normalized.add("{item}+{p}".format(**locals()))
        elif raise_err:
            raise ValueError(item)

    return normalized

def check_encapsulates(root, child, sep="/"):
    """
    Check that one scope item is a sub-item of another.

    This is used to implement sub-scopes, where permissions granted on
    a broad scope can be used to imply permissions for a sub-scope. By default,
    sub-scopes are denoted by a preceeding '/'.

    For example, a scope permission if 'user+r' is granted to an agent, then
    that agent is also implied to have been granted 'user/emails+r', 
    'user/friends+r' and so on.
    """

    root_fragment, root_permissions = root.split("+")
    child_fragment, child_permissions = child.split("+")

    root_fragment = root_fragment[:-1] if root_fragment.endswith(sep) else root_fragment
    # Use a regular expression to verify that the child fragment is indeed a sub
    # scope of the root fragment. It checks
    rep = re.compile("^({0})$|({0})/".format(re.escape(root_fragment)), re.U)

    root_permissions = set(root_permissions)
    child_permissions = set(child_permissions)

    if not root_permissions.issuperset(child_permissions):
        return False

    elif not rep.match(child_fragment):
        return False

    else:
        return True

def compress_scope_items(scopes, default_mode="r"):
    """
    Return a set of equivalent scope items that may
    be smaller in size.

    Input scope items must be a normalized set of scope
    items.

    """
    item_hash = {}
    compressed = set()
    default_permissions = set(default_mode)

    # Catalog which permissions have been collected for each scope item
    # fragment
    for item in scopes:
        fragment, p = item.split("+")
        item_hash.setdefault(fragment, set())
        item_hash[fragment].update(p)

    # Rebuild the set of scopes from catalog, dropping
    # fragments that are covered by shorter fragments
    # in the catalog
    for fragment in item_hash:
        permissions = item_hash[fragment]
        parts = fragment.split("/")

        for i in range(len(parts)):
            frag = "/".join(parts[:i])
            if item_hash.get(frag, set()).issuperset(permissions):
                break
        else:
            if permissions ==  default_permissions:
                compressed.add(fragment)
            else:
                compressed.add("+".join((fragment, "".join(permissions))))

    return compressed

