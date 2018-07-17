import logging
import json
import webbrowser
import urllib
from requests_oauthlib import OAuth2Session
from http.server import HTTPServer, BaseHTTPRequestHandler


LOG = logging.getLogger('strvup.oauth')


class OAuthCallbackRequestHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args, **kwargs):
        pass

    def do_GET(self):
        LOG.debug('callback %s: %s', self.command, self.path)

        setattr(self.server, 'auth_request', self.path)

        self.send_response(200)
        self.end_headers()

        self.wfile.write(b'OK')

def check_oauth(config_path):
    LOG.debug('read oauth config')
    with open(config_path) as ifd:
        config = json.load(ifd)

    oa_client = OAuth2Session(
        client_id=config.get('client_id'),
        redirect_uri=config.get('redirect_uri'),
        scope=['write'],
        token=config.get('token'),
    )

    if oa_client.authorized:
        LOG.info('using previous authorization')
        return oa_client

    LOG.info('run authorization')

    url, _ = oa_client.authorization_url(
        'https://www.strava.com/oauth/authorize'
    )

    LOG.debug('open a browser')
    webbrowser.open(url)

    callback = urllib.parse.urlparse(config['redirect_uri'])
    httpd = HTTPServer(
        (callback.hostname, callback.port),
        OAuthCallbackRequestHandler
    )

    LOG.debug('launch http callback server')
    httpd.handle_request()
    httpd.server_close()
    LOG.debug('served callback')

    parts = urllib.parse.urlparse(getattr(httpd, 'auth_request'))
    query = urllib.parse.parse_qs(parts.query)

    LOG.debug('callback query %r', query)
    token = oa_client.fetch_token(
        'https://www.strava.com/oauth/token',
        code=query['code'][0],
        client_secret=config['client_secret'],
    )

    LOG.debug('token: %r', token)

    config['token'] = token
    with open(config_path, 'w') as ofd:
        json.dump(config, ofd, indent=2)

    return oa_client
