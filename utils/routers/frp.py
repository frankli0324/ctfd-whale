import warnings

from flask import current_app
from requests import session, RequestException

from CTFd.utils import get_config, set_config, logging

from .base import BaseRouter
from ..cache import CacheProvider
from ..exceptions import WhaleError, WhaleWarning
from ..db import DBContainer
from ...models import WhaleContainer


class FrpRouter(BaseRouter):
    name = "frp"
    types = {
        'direct': 'tcp',
        'http': 'http',
    }
    rules = {}

    class FrpRule:
        def __init__(self, name, config):
            self.name = name
            self.config = config

        def __str__(self) -> str:
            return f'[{self.name}]\n' + '\n'.join(f'{k} = {v}' for k, v in self.config.items())

    def __init__(self):
        super().__init__()
        self.ses = session()
        self.url = get_config("whale:frp_api_url").rstrip("/")
        self.common = ''
        try:
            CacheProvider(app=current_app).init_port_sets()
        except Exception:
            warnings.warn(
                "cache initialization failed",
                WhaleWarning
            )
        for container in DBContainer.get_all_alive_container():
            self.register(container)

    def reload(self):
        try:
            if not self.common:
                common = get_config("whale:frp_config_template", '')
                if '[common]' in common:
                    self.common = common
                else:
                    remote = self.ses.get(f'{self.url}/api/config')
                    assert remote.status_code == 200
                    set_config("whale:frp_config_template", remote.text)
                    self.common = remote.text
            config = self.common + '\n'.join(str(r) for r in self.rules.values())
            assert self.ses.put(
                f'{self.url}/api/config', config, timeout=5
            ).status_code == 200
            assert self.ses.get(
                f'{self.url}/api/reload', timeout=5
            ).status_code == 200
        except (RequestException, AssertionError) as e:
            raise WhaleError(
                '\nfrpc request failed\n' +
                (f'{e}\n' if str(e) else '') +
                'please check the frp related configs'
            ) from None

    def register(self, container: WhaleContainer):
        name = f'{container.challenge.redirect_type}_{container.user_id}_{container.uuid}'
        config = {
            'type': self.types[container.challenge.redirect_type],
            'local_ip': f'{container.user_id}-{container.uuid}',
            'local_port': container.challenge.redirect_port,
            'use_compression': 'true',
        }
        if container.challenge.redirect_type == 'direct':
            port = CacheProvider(app=current_app).get_available_port()
            if not port:
                return False, 'No available ports. Please wait for a few minutes.'
            config['remote_port'] = port
        elif container.challenge.redirect_type == 'http':
            config['subdomain'] = container.http_subdomain
        self.rules[container.id] = self.FrpRule(name, config)
        self.reload()
        return True, 'success'

    def unregister(self, container: WhaleContainer):
        rule = self.rules.pop(container.id)
        if container.challenge.redirect_type == 'direct':
            try:
                redis_util = CacheProvider(app=current_app)
                redis_util.add_available_port(rule.config['remote_port'])
            except Exception as e:
                logging.log(
                    'whale', 'Error deleting port from cache',
                    name=container.user.name,
                    challenge_id=container.challenge_id,
                )
                return False, 'Error deleting port from cache'
        self.reload()
        return True, 'success'

    def check_availability(self):
        try:
            resp = self.ses.get(f'{self.url}/api/status')
        except RequestException as e:
            return False, 'Unable to access frpc admin api'
        if resp.status_code == 401:
            return False, 'frpc admin api unauthorized'
        return True, 'Available'
