import unittest
from scripts.ptw_caddy_configuration import render

class CaddyConfigurationTests(unittest.TestCase):
    def test_environment_host_retains_security_and_unrelated_routes(self):
        source = '{\n admin off\n}\n(security_headers) {\n header -Server\n}\n{$COMMANDER_PUBLIC_HOST} {\n import security_headers\n handle {\n reverse_proxy old:8088\n }\n}\n:8080 { respond "OK" }\n'
        fragment = 'commander.proove-them-wrong.com {\n reverse_proxy new:8088\n}\n'
        result = render(source, fragment)
        self.assertTrue(result.startswith('{\n admin off\n}\n(security_headers)'))
        self.assertTrue(result.endswith(':8080 { respond "OK" }\n'))
        self.assertIn('import security_headers', result)
        self.assertIn('reverse_proxy new:8088', result)
        self.assertNotIn('reverse_proxy old:8088', result)

    def test_missing_or_duplicate_host_is_rejected(self):
        fragment = 'commander.proove-them-wrong.com { respond "OK" }'
        for source in (':8080 { respond "OK" }', fragment + '\n' + fragment):
            with self.assertRaises(ValueError):
                render(source, fragment)
