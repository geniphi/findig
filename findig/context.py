from werkzeug.local import Local


# A global context local
ctx = Local()

# A bunch of context local proxies
request = ctx('request')
url_adapter = ctx('url_adapter')
app = ctx('app')
url_values = ctx('url_values')
dispatcher = ctx('dispatcher')
resource = ctx('resource')


__all__ = ['ctx', 'request', 'url_adapter', 'app', 'url_values', 
           'dispatcher', 'resource']
