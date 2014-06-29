from werkzeug.local import Local


# A global context local
ctx = Local()

# A bunch of context local proxies
request = ctx('request')
url_adapter = ctx('url_adapter')


__all__ = 'ctx', 'request', 'url_adapter'