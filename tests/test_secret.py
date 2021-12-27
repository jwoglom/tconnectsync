#!/usr/bin/env python3

import unittest
import unittest.mock
import tempfile
import importlib
import contextlib
import pathlib
import os

@contextlib.contextmanager
def chdir(dir):
    orig_cwd = os.getcwd()
    os.chdir(dir)

    try:
        yield
    finally:
        os.chdir(orig_cwd)

class TestSecretDotEnv(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        if 'TCONNECT_EMAIL' in os.environ:
            del os.environ['TCONNECT_EMAIL']

        if 'NS_URL' in os.environ:
            del os.environ['NS_URL']

    def write_test_dotenv_file(self, path, type):
        with open(os.path.join(path, ".env"), "w") as f:
            f.write("""
TCONNECT_EMAIL=test_%s_email@email.com
NS_URL=http://test_%s_url
            """ % (type, type))
            f.close()
    
    def import_secret(self):
        return importlib.reload(importlib.import_module("tconnectsync.secret"))

    def test_dotenv_in_current_working_directory(self):
        with tempfile.TemporaryDirectory(prefix='dotenv_cwd') as dir, chdir(dir):
            self.write_test_dotenv_file(dir, "dotenv_cwd")

            secret = self.import_secret()
            self.assertEqual(secret.TCONNECT_EMAIL, "test_dotenv_cwd_email@email.com")
            self.assertEqual(secret.NS_URL, "http://test_dotenv_cwd_url")

    def test_dotenv_in_homedir_config_folder(self):
        with tempfile.TemporaryDirectory(prefix='dotenv_homedir_config') as dir, chdir(dir):
            config_dir = os.path.join(dir, '.config/tconnectsync')
            os.makedirs(config_dir)

            self.write_test_dotenv_file(config_dir, "dotenv_homedir_config")

            with unittest.mock.patch.object(pathlib.Path, "home") as mock_home:
                mock_home.return_value = dir

                secret = self.import_secret()
                self.assertEqual(secret.TCONNECT_EMAIL, "test_dotenv_homedir_config_email@email.com")
                self.assertEqual(secret.NS_URL, "http://test_dotenv_homedir_config_url")

    def test_no_dotenv_file_reads_from_environment(self):
        with tempfile.TemporaryDirectory(prefix='dotenv_environ') as dir, chdir(dir):
            environ = {
                "TCONNECT_EMAIL": "test_environ_email@email.com", 
                "NS_URL": "http://test_environ_url"
            }

            with unittest.mock.patch.dict(os.environ, environ):
                secret = self.import_secret()
                self.assertEqual(secret.TCONNECT_EMAIL, environ["TCONNECT_EMAIL"])
                self.assertEqual(secret.NS_URL, environ["NS_URL"])

    def test_environment_merges_with_dotenv_file(self):
        with tempfile.TemporaryDirectory(prefix='env_plus_environ') as dir, chdir(dir):
            self.write_test_dotenv_file(dir, "dotenv_cwd_defaults")

            environ = {
                "TCONNECT_EMAIL": "test_environ_override_email@email.com"
            }

            with unittest.mock.patch.dict(os.environ, environ):
                secret = self.import_secret()
                self.assertEqual(secret.TCONNECT_EMAIL, "test_environ_override_email@email.com")
                self.assertEqual(secret.NS_URL, "http://test_dotenv_cwd_defaults_url")

    def test_dotenv_in_current_working_directory_overrides_homedir_config(self):
        with tempfile.TemporaryDirectory(prefix='dotenv_cwd') as dir, chdir(dir):
            self.write_test_dotenv_file(dir, "dotenv_cwd")

            config_dir = os.path.join(dir, '.config/tconnectsync')
            os.makedirs(config_dir)

            self.write_test_dotenv_file(config_dir, "dotenv_homedir_config")

            with unittest.mock.patch.object(pathlib.Path, "home") as mock_home:
                mock_home.return_value = dir

                secret = self.import_secret()
                self.assertEqual(secret.TCONNECT_EMAIL, "test_dotenv_cwd_email@email.com")
                self.assertEqual(secret.NS_URL, "http://test_dotenv_cwd_url")

if __name__ == '__main__':
    unittest.main()