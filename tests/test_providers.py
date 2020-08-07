import unittest
import json
import time
import requests

from alibabacloud_credentials.credentials import AccessKeyCredential
from alibabacloud_credentials import providers, models, credentials, exceptions
from alibabacloud_credentials.utils import auth_util
from . import ini_file

import threading
from http.server import HTTPServer, BaseHTTPRequestHandler


class Request(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{"Code": "Success", "AccessKeyId": "ak",'
                         b' "Expiration": "3999-08-07T20:20:20Z", "Credentials":'
                         b' {"Expiration": "3999-08-07T20:20:20Z"}, "SessionAccessKey":'
                         b' {"Expiration": "3999-08-07T20:20:20Z"}}')


def run_server():
    server = HTTPServer(('localhost', 8888), Request)
    server.serve_forever()


class TestProviders(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server = threading.Thread(target=run_server)
        server.setDaemon(True)
        server.start()

    @staticmethod
    def strftime(t):
        return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.localtime(t))

    def test_EcsRamRoleCredentialProvider(self):
        prov = providers.EcsRamRoleCredentialProvider("roleName")
        self.assertIsNotNone(prov)
        self.assertEqual("roleName", prov.role_name)

        cfg = models.Config()
        cfg.role_name = "roleNameConfig"
        cfg.timeout = 1100
        cfg.connect_timeout = 1200
        prov = providers.EcsRamRoleCredentialProvider(config=cfg)
        self.assertIsNotNone(prov)
        self.assertEqual("roleNameConfig", prov.role_name)
        self.assertEqual(2300, prov.timeout)
        # prov._create_credential(url='http://www.aliyun.com')
        cred = prov._create_credential(url='http://127.0.0.1:8888')
        self.assertEqual('ak', cred.access_key_id)
        self.assertEqual('3999-08-07T20:20:20Z', self.strftime(cred.expiration))

        prov._get_role_name(url='http://www.aliyun.com')
        self.assertIsNotNone(prov.role_name)
        prov.role_name = 'role_name'
        prov._set_credential_url()
        self.assertEqual('http://100.100.100.200/latest/meta-data/ram/security-credentials/role_name', prov.credential_url)

    def test_DefaultCredentialsProvider(self):
        prov = providers.DefaultCredentialsProvider()
        p = providers.EnvironmentVariableCredentialsProvider()

        # add_credentials_provider
        prov.add_credentials_provider(p)
        self.assertTrue(prov.user_configuration_providers.__contains__(p))

        # contains_credentials_provider
        res = prov.contains_credentials_provider(p)
        self.assertTrue(res)

        # remove_credentials_provider
        prov.remove_credentials_provider(p)
        self.assertFalse(prov.user_configuration_providers.__contains__(p))

        # clear_credentials_provider
        prov.add_credentials_provider(p)
        prov.add_credentials_provider(p)
        prov.clear_credentials_provider()
        self.assertEqual([], prov.user_configuration_providers)

        # not found credentials
        try:
            prov.get_credentials()
        except Exception as e:
            self.assertEqual('not found credentials', e.message)

        prov.add_credentials_provider(p)
        prov.clear_credentials_provider()
        self.assertRaises(exceptions.CredentialException, prov.get_credentials)

    def test_RamRoleArnCredentialProvider(self):
        access_key_id, access_key_secret, role_session_name, role_arn, region_id, policy = \
            'access_key_id', 'access_key_secret', 'role_session_name', 'role_arn', 'region_id', 'policy'
        prov = providers.RamRoleArnCredentialProvider(
            access_key_id, access_key_secret, role_session_name, role_arn, region_id, policy
        )
        self.assertEqual('access_key_id', prov.access_key_id)
        self.assertEqual('access_key_secret', prov.access_key_secret)
        self.assertEqual('role_session_name', prov.role_session_name)
        self.assertEqual('role_arn', prov.role_arn)
        self.assertEqual('region_id', prov.region_id)
        self.assertEqual('policy', prov.policy)

        conf = models.Config(
            access_key_id=access_key_id,
            access_key_secret=access_key_secret,
            role_session_name=role_session_name,
            role_arn=role_arn
        )
        prov = providers.RamRoleArnCredentialProvider(config=conf)
        self.assertEqual('access_key_id', prov.access_key_id)
        self.assertEqual('access_key_secret', prov.access_key_secret)
        self.assertEqual('role_session_name', prov.role_session_name)
        self.assertEqual('role_arn', prov.role_arn)
        self.assertEqual('cn-hangzhou', prov.region_id)
        self.assertIsNone(prov.policy)

        cred = prov._create_credentials(turl='http://127.0.0.1:8888')
        self.assertEqual('3999-08-07T20:20:20Z', self.strftime(cred.expiration))

    def test_RsaKeyPairCredentialProvider(self):
        access_key_id, access_key_secret, region_id = \
            'access_key_id', 'access_key_secret', 'region_id'
        prov = providers.RsaKeyPairCredentialProvider(
            access_key_id, access_key_secret, region_id
        )
        self.assertEqual('access_key_id', prov.access_key_id)
        self.assertEqual('access_key_secret', prov.access_key_secret)
        self.assertEqual('region_id', prov.region_id)

        conf = models.Config(
            access_key_id=access_key_id,
            access_key_secret=access_key_secret
        )
        prov = providers.RsaKeyPairCredentialProvider(config=conf)
        self.assertEqual('access_key_id', prov.access_key_id)
        self.assertEqual('access_key_secret', prov.access_key_secret)
        self.assertEqual('cn-hangzhou', prov.region_id)

        cred = prov._create_credential(turl='http://127.0.0.1:8888')
        self.assertEqual('3999-08-07T20:20:20Z', self.strftime(cred.expiration))

    def test_ProfileCredentialsProvider(self):
        prov = providers.ProfileCredentialsProvider(ini_file)
        auth_util.client_type = 'default'
        c = prov.get_credentials()
        self.assertIsInstance(c, credentials.AccessKeyCredential)
        auth_util.client_type = 'client2'
        self.assertRaises(exceptions.CredentialException, prov.get_credentials)

        auth_util.client_type = 'client4'
        auth_util.environment_access_key_secret = 'test'
        self.assertRaises(exceptions.CredentialException, prov.get_credentials)

        auth_util.client_type = 'client1'
        self.assertRaises(requests.exceptions.ConnectTimeout, prov.get_credentials)

        auth_util.client_type = 'client6'
        self.assertIsNone(prov.get_credentials())
        auth_util.client_type = 'client7'
        self.assertIsNone(prov.get_credentials())
        prov = providers.ProfileCredentialsProvider()
        self.assertIsNone(prov.get_credentials())

    def test_EnvironmentVariableCredentialsProvider(self):
        prov = providers.EnvironmentVariableCredentialsProvider()
        auth_util.client_type = 'aa'
        self.assertEqual(None, prov.get_credentials())

        auth_util.client_type = 'default'
        auth_util.environment_access_key_id = 'accessKeyIdTest'
        self.assertIsNone(prov.get_credentials())

        auth_util.environment_access_key_secret = 'accessKeySecretTest'
        cred = prov.get_credentials()
        self.assertEqual('accessKeyIdTest', cred.access_key_id)
        self.assertEqual('accessKeySecretTest', cred.access_key_secret)

        auth_util.environment_access_key_id = None
        self.assertIsNone(prov.get_credentials())

        auth_util.environment_access_key_id = ''
        self.assertRaises(exceptions.CredentialException, prov.get_credentials)

        auth_util.environment_access_key_id = 'a'
        auth_util.environment_access_key_secret = ''
        self.assertRaises(exceptions.CredentialException, prov.get_credentials)



