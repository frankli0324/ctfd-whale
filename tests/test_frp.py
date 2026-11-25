"""Run with Python 3.11+: python3 -m unittest discover -s tests -v.

Isolate CTFd, Redis and HTTP so config generation needs no running services.
"""
import importlib.util
from pathlib import Path
import sys
import tomllib
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
INI = '[common]\nserver_addr = frps\nserver_port = 7000\n'
TOML = 'serverAddr = "frps"\nserverPort = 7000\n[webServer]\nport = 7400\n'


def load_frp():
    """Load the router without executing the plugin's CTFd startup hooks."""
    modules = {}
    for name in ('CTFd', '_whale_test', '_whale_test.utils', '_whale_test.utils.routers'):
        modules[name] = ModuleType(name)
        modules[name].__path__ = []
    dependencies = {
        'flask': dict(current_app=Mock()),
        'requests': dict(session=Mock(), RequestException=type('RequestException', (Exception,), {})),
        'CTFd.models': dict(db=Mock()),
        'CTFd.utils': dict(get_config=Mock(), set_config=Mock(), logging=Mock()),
        '_whale_test.models': dict(WhaleContainer=SimpleNamespace),
        '_whale_test.utils.routers.base': dict(BaseRouter=object),
        '_whale_test.utils.cache': dict(CacheProvider=Mock()),
        '_whale_test.utils.db': dict(DBContainer=Mock()),
        '_whale_test.utils.exceptions': dict(
            WhaleError=type('WhaleError', (Exception,), {}),
            WhaleWarning=type('WhaleWarning', (Warning,), {}),
        ),
    }
    for name, attributes in dependencies.items():
        modules[name] = ModuleType(name)
        modules[name].__dict__.update(attributes)
    spec = importlib.util.spec_from_file_location(
        '_whale_test.utils.routers.frp', ROOT / 'utils/routers/frp.py'
    )
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, modules):
        spec.loader.exec_module(module)
    return module


def container(kind, uuid, port=10001):
    return SimpleNamespace(
        uuid=uuid, user_id=7, port=port, http_subdomain='web',
        challenge=SimpleNamespace(redirect_type=kind, redirect_port=3000),
    )


class FrpConfigTests(unittest.TestCase):
    def setUp(self):
        self.frp = load_frp()
        self.settings = {'whale:frp_api_url': 'http://frpc:7400/', 'whale:frp_config_template': INI}
        self.frp.get_config.side_effect = lambda key, default=None: self.settings.get(key, default)
        self.frp.set_config.side_effect = self.settings.__setitem__
        self.router = self.frp.FrpRouter()
        self.session = self.router.ses
        self.session.get.return_value = SimpleNamespace(status_code=200, text=INI)
        self.session.put.return_value = SimpleNamespace(status_code=200)
        self.frp.DBContainer.get_all_alive_container.return_value = [
            container('direct', 'tcp-id'), container('http', 'http-id'),
        ]

    def output(self):
        output = self.session.put.call_args.args[1]
        return output.decode('utf-8') if isinstance(output, bytes) else output

    def use_toml(self, template=TOML):
        self.settings['whale:frp_config_format'] = 'toml'
        self.settings['whale:frp_config_template'] = template

    def test_ini_default_matches_legacy_output(self):
        self.router.reload()
        self.assertEqual(self.output(), INI + '\n' + (
            '[direct_7_tcp-id]\n'
            'type = tcp\nlocal_ip = 7-tcp-id\nlocal_port = 3000\n'
            'use_compression = true\nremote_port = 10001\n'
            '[http_7_http-id]\n'
            'type = http\nlocal_ip = 7-http-id\nlocal_port = 3000\n'
            'use_compression = true\nsubdomain = web'
        ))
        self.frp.set_config.assert_not_called()
        self.session.get.assert_called_once_with('http://frpc:7400/api/reload', timeout=5)

    def test_explicit_ini_excludes_removed_container(self):
        self.settings['whale:frp_config_format'] = 'ini'
        self.router.reload(exclude='tcp-id')
        self.assertNotIn('tcp-id', self.output())
        self.assertIn('[http_7_http-id]', self.output())

    def test_ini_fetches_missing_common_template(self):
        self.settings['whale:frp_config_template'] = ''
        self.router.reload()
        self.assertEqual(self.settings['whale:frp_config_template'], INI)
        self.assertEqual(self.session.get.call_args_list[0].args, ('http://frpc:7400/api/config',))

    def test_toml_http_and_tcp_types_and_escaping(self):
        self.use_toml()
        tcp, http = self.frp.DBContainer.get_all_alive_container.return_value
        tcp.port = '10001'
        tcp.challenge.redirect_port = '3000'
        http.http_subdomain = 'quote"\\line\n\u00e9\U00010000\x7f'
        self.router.reload()
        self.assertIsInstance(self.session.put.call_args.args[1], bytes)
        parsed = tomllib.loads(self.output())
        self.assertEqual(parsed['webServer'], {'port': 7400})
        self.assertEqual(parsed['proxies'], [
            {'name': 'direct_7_tcp-id', 'type': 'tcp', 'localIP': '7-tcp-id',
             'localPort': 3000, 'remotePort': 10001, 'transport': {'useCompression': True}},
            {'name': 'http_7_http-id', 'type': 'http', 'localIP': '7-http-id',
             'localPort': 3000, 'subdomain': http.http_subdomain,
             'transport': {'useCompression': True}},
        ])
        self.assertNotIn('[common]', self.output())

    def test_toml_import_drops_old_rules_before_regenerating(self):
        self.use_toml('')
        self.session.get.return_value.text = TOML + (
            '  [[ proxies ]] # previously generated\nname = "old"\ntype = "tcp"\n'
        )
        self.router.reload(exclude='http-id')
        self.assertEqual(self.settings['whale:frp_config_template'].strip(), TOML.strip())
        self.assertEqual(len(tomllib.loads(self.output())['proxies']), 1)
        self.assertNotIn('old', self.output())
        # A fresh worker importing the resulting frpc file must not duplicate rules.
        self.session.get.return_value.text = self.output()
        self.settings['whale:frp_config_template'] = ''
        self.router.common = ''
        self.router.reload(exclude='http-id')
        self.assertEqual(len(tomllib.loads(self.output())['proxies']), 1)

    def test_toml_empty_container_list_keeps_only_shared_settings(self):
        self.use_toml(TOML + '[[visitors]]\nname = "old"\n')
        self.frp.DBContainer.get_all_alive_container.return_value = []
        self.router.reload()
        self.assertEqual(tomllib.loads(self.output()), tomllib.loads(TOML))

    def test_switching_formats_clears_cached_template(self):
        self.router.reload()
        self.use_toml()
        self.router.reload()
        self.assertEqual(len(tomllib.loads(self.output())['proxies']), 2)
        self.settings['whale:frp_config_format'] = 'ini'
        self.settings['whale:frp_config_template'] = INI
        self.router.reload()
        self.assertTrue(self.output().startswith(INI))
        self.assertNotIn('[[proxies]]', self.output())

    def test_toml_rejects_remote_ini_before_writing(self):
        self.use_toml(INI)
        for _ in range(2):
            with self.assertRaisesRegex(self.frp.WhaleError, 'Configure frpc'):
                self.router.reload()
        self.session.put.assert_not_called()

    def test_invalid_format_does_not_write_config(self):
        self.settings['whale:frp_config_format'] = 'yaml'
        with self.assertRaisesRegex(self.frp.WhaleError, 'ini or toml'):
            self.router.reload()
        self.session.put.assert_not_called()

    def test_request_failure_keeps_existing_error_handling(self):
        self.use_toml()
        self.session.put.side_effect = self.frp.RequestException('offline')
        with self.assertRaisesRegex(self.frp.WhaleError, 'frpc request failed'):
            self.router.reload()


if __name__ == '__main__':
    unittest.main()
