#  Licensed under the Apache License, Version 2.0 (the "License"); you may
#  not use this file except in compliance with the License. You may obtain
#  a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#  WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#  License for the specific language governing permissions and limitations
#  under the License.
import argparse
import logging
import types
import unittest

from openstack import exceptions as os_exceptions

from ospurge import exceptions
from ospurge import main
from ospurge.resources.base import ServiceResource
from ospurge.tests import mock


try:
    SimpleNamespace = types.SimpleNamespace   # Python 3.3+
except AttributeError:
    class SimpleNamespace(object):   # Python 2.7
        def __init__(self, **attr):
            self.__dict__.update(attr)


class TestFunctions(unittest.TestCase):
    @mock.patch('logging.basicConfig', autospec=True)
    def test_configure_logging_verbose(self, m_basicConfig):
        main.configure_logging(verbose=True)
        m_basicConfig.assert_called_with(format=mock.ANY, level=logging.INFO)

    @mock.patch('logging.basicConfig', autospec=True)
    def test_configure_logging(self, m_basicConfig):
        main.configure_logging(verbose=False)
        m_basicConfig.assert_called_with(format=mock.ANY, level=logging.WARN)

    def test_create_argument_parser_with_purge_project(self):
        parser = main.create_argument_parser()
        self.assertIsInstance(parser, argparse.ArgumentParser)

        options = parser.parse_args([
            '--verbose', '--dry-run', '--purge-project', 'foo',
            '--delete-shared-resources'
        ])
        self.assertEqual(True, options.verbose)
        self.assertEqual(True, options.dry_run)
        self.assertEqual(True, options.delete_shared_resources)
        self.assertEqual('foo', options.purge_project)

    def test_create_argument_parser_with_purge_own_project(self):
        parser = main.create_argument_parser()
        options = parser.parse_args(['--purge-own-project'])

        self.assertEqual(False, options.verbose)
        self.assertEqual(False, options.dry_run)
        self.assertEqual(False, options.delete_shared_resources)
        self.assertEqual(True, options.purge_own_project)

    def test_create_argument_parser_with_resource(self):
        parser = main.create_argument_parser()
        self.assertIsInstance(parser, argparse.ArgumentParser)

        options = parser.parse_args([
            '--resource', 'Networks', '--purge-project', 'foo',
            '--resource', 'Volumes'
        ])
        self.assertEqual('foo', options.purge_project)
        self.assertEqual(['Networks', 'Volumes'], options.resource)

    def test_runner_delete(self):
        resources = [mock.Mock(), mock.Mock(), mock.Mock()]
        resource_manager = mock.Mock(list=mock.Mock(return_value=resources))
        options = mock.Mock(dry_run=False, resource=False, disable_only=False)
        exit = mock.Mock(is_set=mock.Mock(side_effect=[False, False, True]))

        main.runner(resource_manager, options, exit)

        resource_manager.list.assert_called_once_with()
        resource_manager.wait_for_check_prerequisite.assert_called_once_with(
            exit)
        self.assertEqual(
            [mock.call(resources[0]), mock.call(resources[1])],
            resource_manager.should_delete.call_args_list
        )
        self.assertEqual(2, resource_manager.delete.call_count)
        self.assertEqual(
            [mock.call(resources[0]), mock.call(resources[1])],
            resource_manager.delete.call_args_list
        )

    def test_runner_disable(self):
        resources = [mock.Mock(), mock.Mock(), mock.Mock()]
        resource_manager = mock.Mock(list=mock.Mock(return_value=resources))
        options = mock.Mock(dry_run=False, resource=False, disable_only=True)
        exit = mock.Mock(is_set=mock.Mock(side_effect=[False, False, True]))

        main.runner(resource_manager, options, exit)

        resource_manager.list.assert_called_once_with()
        resource_manager.wait_for_check_prerequisite.assert_not_called()
        resource_manager.should_delete.assert_not_called()
        resource_manager.delete.assert_not_called()
        self.assertEqual(2, resource_manager.disable.call_count)
        self.assertEqual(
            [mock.call(resources[0]), mock.call(resources[1])],
            resource_manager.disable.call_args_list
        )

    def test_runner_disable_dry_run(self):
        resources = [mock.Mock(), mock.Mock(), mock.Mock()]
        resource_manager = mock.Mock(list=mock.Mock(return_value=resources))
        options = mock.Mock(dry_run=True, resource=False, disable_only=True)
        exit = mock.Mock(is_set=mock.Mock(side_effect=[False, False, True]))

        main.runner(resource_manager, options, exit)

        resource_manager.list.assert_called_once_with()
        resource_manager.wait_for_check_prerequisite.assert_not_called()
        resource_manager.should_delete.assert_not_called()
        resource_manager.delete.assert_not_called()
        resource_manager.disable.assert_not_called()
        resource_manager.assert_not_called()

    def test_runner_delete_dry_run(self):
        resources = [mock.Mock(), mock.Mock()]
        resource_manager = mock.Mock(list=mock.Mock(return_value=resources))
        options = mock.Mock(dry_run=True, disable_only=False)
        exit = mock.Mock(is_set=mock.Mock(return_value=False))

        main.runner(resource_manager, options, exit)

        resource_manager.wait_for_check_prerequisite.assert_not_called()
        resource_manager.delete.assert_not_called()

    def test_runner_resource(self):
        resources = [mock.Mock()]
        resource_manager = mock.Mock(list=mock.Mock(return_value=resources))
        options = mock.Mock(dry_run=False, resource=True, disable_only=False)
        exit = mock.Mock(is_set=mock.Mock(return_value=False))
        main.runner(resource_manager, options, exit)
        resource_manager.wait_for_check_prerequisite.assert_not_called()
        resource_manager.delete.assert_called_once_with(mock.ANY)

    def test_runner_with_unrecoverable_exception(self):
        resource_manager = mock.Mock(list=mock.Mock(side_effect=Exception))
        exit = mock.Mock()

        main.runner(resource_manager, mock.Mock(dry_run=True), exit)

        exit.set.assert_called_once_with()

    def test_runner_with_recoverable_exception(self):
        class MyEndpointNotFound(Exception):
            pass
        exc = os_exceptions.OpenStackCloudException("")
        exc.inner_exception = (MyEndpointNotFound, )
        resource_manager = mock.Mock(list=mock.Mock(side_effect=exc))
        exit = mock.Mock()

        main.runner(resource_manager, mock.Mock(dry_run=True), exit)
        self.assertEqual(1, resource_manager.list.call_count)
        self.assertFalse(exit.set.called)

        resource_manager = mock.Mock(
            list=mock.Mock(side_effect=MyEndpointNotFound))
        main.runner(resource_manager, mock.Mock(dry_run=True), exit)
        self.assertEqual(1, resource_manager.list.call_count)
        self.assertFalse(exit.set.called)

    @mock.patch.object(main, 'connection')
    @mock.patch.object(main, 'loader', autospec=True)
    @mock.patch('argparse.ArgumentParser.parse_args')
    @mock.patch('threading.Event', autospec=True)
    @mock.patch('concurrent.futures.ThreadPoolExecutor', autospec=True)
    @mock.patch('sys.exit', autospec=True)
    def test_main(self, m_sys_exit, m_tpe, m_event, m_parse_args,
                  m_oscc, m_conn):
        m_tpe.return_value.__enter__.return_value.map.side_effect = \
            KeyboardInterrupt
        m_parse_args.return_value.purge_own_project = False
        m_parse_args.return_value.resource = None
        m_conn.Connection().get_project().is_enabled = False

        main.main()

        m_oscc.OpenStackConfig.assert_called_once_with()

        m_parse_args.assert_called_once_with()

        self.assertIsInstance(m_tpe.call_args[0][0], int)
        m_tpe.return_value.__enter__.assert_called_once_with()
        self.assertEqual(1, m_tpe.return_value.__exit__.call_count)

        executor = m_tpe.return_value.__enter__.return_value
        self.assertEqual(1, executor.map.call_count)
        map_args = executor.map.call_args[0]
        self.assertEqual(True, callable(map_args[0]))
        for obj in map_args[1]:
            self.assertIsInstance(obj, ServiceResource)

        m_event.return_value.set.assert_called_once_with()
        m_event.return_value.is_set.assert_called_once_with()
        self.assertIsInstance(m_sys_exit.call_args[0][0], int)

    @mock.patch.object(main, 'connection')
    @mock.patch.object(main, 'loader', autospec=True)
    @mock.patch('argparse.ArgumentParser.parse_args')
    @mock.patch('threading.Event', autospec=True)
    @mock.patch('concurrent.futures.ThreadPoolExecutor', autospec=True)
    @mock.patch('sys.exit', autospec=True)
    def test_main_resource(self, m_sys_exit, m_tpe, m_event, m_parse_args,
                           m_oscc, m_conn):
        m_tpe.return_value.__enter__.return_value.map.side_effect = \
            KeyboardInterrupt
        m_parse_args.return_value.purge_own_project = False
        m_parse_args.return_value.resource = "Networks"
        m_conn.Connection().identity.get_tenant().is_enabled = False
        main.main()
        m_tpe.return_value.__enter__.assert_called_once_with()
        executor = m_tpe.return_value.__enter__.return_value
        map_args = executor.map.call_args[0]
        for obj in map_args[1]:
            self.assertIsInstance(obj, ServiceResource)


@mock.patch.object(main, 'loader')
@mock.patch.object(main, 'connection')
class TestCredentialsManager(unittest.TestCase):
    def test_init_with_purge_own_project(self, m_conn, m_osc):
        _options = SimpleNamespace(
            purge_own_project=True, purge_project=None)
        _config = m_osc.OpenStackConfig()
        creds_manager = main.CredentialsManager(_options, _config)

        self.assertEqual(_options, creds_manager.options)
        self.assertEqual(False, creds_manager.revoke_role_after_purge)
        self.assertEqual(False, creds_manager.disable_project_after_purge)
        self.assertEqual(m_conn.Connection.return_value,
                         creds_manager.cloud)

        m_conn.Connection.assert_called_once_with(
            config=_config.get_one())
        self.assertEqual(m_conn.Connection.return_value,
                         creds_manager.cloud)

        self.assertEqual(
            creds_manager.cloud.current_user_id,
            creds_manager.user_id
        )
        self.assertEqual(
            creds_manager.cloud.current_project_id,
            creds_manager.project_id
        )
        self.assertEqual(
            creds_manager.cloud.current_project.name,
            creds_manager.project_name
        )

    def test_init_with_purge_project(self, m_conn, m_osc):
        _config = m_osc.OpenStackConfig()
        _options = SimpleNamespace(
            purge_own_project=False, purge_project=mock.sentinel.purge_project)
        creds_manager = main.CredentialsManager(_options, _config)

        m_conn.Connection.assert_called_once_with(config=_config.get_one())
        m_conn.Connection().get_project.assert_called_once_with(
            _options.purge_project)

        self.assertEqual(
            m_conn.Connection.return_value,
            creds_manager.admin_cloud
        )
        self.assertEqual(
            m_conn.Connection().connect_as_project.return_value,
            creds_manager.cloud
        )

        self.assertEqual(
            creds_manager.admin_cloud.current_user_id,
            creds_manager.user_id
        )
        self.assertEqual(
            creds_manager.admin_cloud.get_project().id,
            creds_manager.project_id
        )
        self.assertEqual(
            creds_manager.admin_cloud.get_project().name,
            creds_manager.project_name
        )
        self.assertFalse(creds_manager.disable_project_after_purge)

    def test_init_with_project_not_found(self, m_conn, m_osc):
        m_conn.Connection().get_project.return_value = None
        self.assertRaises(
            exceptions.OSProjectNotFound,
            main.CredentialsManager,
            mock.Mock(purge_own_project=False), m_osc.OpenStackConfig()
        )

    def test_ensure_role_on_project(self, m_conn, m_osc):
        options = mock.Mock(purge_own_project=False)
        config = m_osc.OpenStackConfig()
        creds_manager = main.CredentialsManager(options, config)
        creds_manager.ensure_role_on_project()

        self.assertEqual(
            m_conn.Connection.return_value,
            creds_manager.admin_cloud
        )
        self.assertEqual(
            m_conn.Connection().connect_as_project.return_value,
            creds_manager.cloud
        )

        creds_manager.admin_cloud.grant_role.assert_called_once_with(
            options.admin_role_name, project=options.purge_project,
            user=mock.ANY)
        self.assertEqual(True, creds_manager.revoke_role_after_purge)

        # If purge_own_project is not False, we purge our own project
        # so no need to revoke role after purge
        creds_manager = main.CredentialsManager(
            mock.Mock(), m_osc.OpenStackConfig())
        creds_manager.ensure_role_on_project()
        self.assertEqual(False, creds_manager.revoke_role_after_purge)

    def test_revoke_role_on_project(self, m_conn, m_osc):
        options = mock.Mock(purge_own_project=False)
        config = m_osc.OpenStackConfig()
        creds_manager = main.CredentialsManager(options, config)
        creds_manager.revoke_role_on_project()

        self.assertEqual(
            m_conn.Connection.return_value,
            creds_manager.admin_cloud
        )
        self.assertEqual(
            m_conn.Connection().connect_as_project.return_value,
            creds_manager.cloud
        )

        creds_manager.admin_cloud.revoke_role.assert_called_once_with(
            options.admin_role_name, project=options.purge_project,
            user=mock.ANY)

    def test_ensure_enabled_project(self, m_conn, m_osc):
        m_conn.Connection().get_project().is_enabled = False
        options = mock.Mock(purge_own_project=False)
        creds_manager = main.CredentialsManager(
            options, m_osc.OpenStackConfig())
        creds_manager.ensure_enabled_project()

        self.assertEqual(
            m_conn.Connection.return_value,
            creds_manager.admin_cloud
        )
        self.assertEqual(
            m_conn.Connection().connect_as_project.return_value,
            creds_manager.cloud
        )

        self.assertEqual(True, creds_manager.disable_project_after_purge)
        m_conn.Connection().connect_as_project.assert_called_once_with(
            options.purge_project)
        creds_manager.admin_cloud.update_project.assert_called_once_with(
            mock.ANY, enabled=True)

        # If project is enabled before purge, no need to disable it after
        # purge
        creds_manager = main.CredentialsManager(
            mock.Mock(), m_osc.OpenStackConfig())
        creds_manager.ensure_enabled_project()
        self.assertEqual(False, creds_manager.disable_project_after_purge)
        self.assertEqual(1, m_conn.Connection().update_project.call_count)

    def test_disable_project(self, m_conn, m_osc):
        options = mock.Mock(purge_own_project=False)
        config = m_osc.OpenStackConfig()
        creds_manager = main.CredentialsManager(options, config)
        creds_manager.disable_project()

        self.assertEqual(
            m_conn.Connection.return_value,
            creds_manager.admin_cloud
        )
        self.assertEqual(
            m_conn.Connection().connect_as_project.return_value,
            creds_manager.cloud
        )

        m_conn.Connection().connect_as_project.assert_called_once_with(
            options.purge_project)
        m_conn.Connection().update_project.assert_called_once_with(
            mock.ANY, enabled=False
        )
