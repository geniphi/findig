from warnings import warn
from traceback import print_exc

try:
    from redis_ import *
except ImportError:
    print_exc()
    warn("Redis support is not available. Run `pip install redis` to enable.")

try:
    from jinja import *
except ImportError:
    print_exc()
    warn("Jinja2 support is not available. Run `pip install jinja2` to enable.")