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
import os
import pkg_resources
import types
import typing
import unittest

from openstack import exceptions as os_exceptions
import six

from ospurge.resources.base import ServiceResource
from ospurge.tests import mock
from ospurge import utils


def register_test_entry_point():
    test_resource_file = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__), 'resources/entry_points.py'
        )
    )
    distribution = pkg_resources.Distribution.from_filename(test_resource_file)
    entry_point = pkg_resources.EntryPoint(
        'foo', 'ospurge.tests.resources.entry_points', dist=distribution
    )
    distribution._ep_map = {utils.ENTRY_POINTS_NAME: {'foo': entry_point}}
    pkg_resources.working_set.add(distribution, 'foo')
    return entry_point


class TestUtils(unittest.TestCase):

    def test_load_ospurge_resource_modules(self):
        modules = utils.load_ospurge_resource_modules()
        self.assertIsInstance(modules, typing.Dict)
        for name, module in six.iteritems(modules):
            # assertIsInstance(name, typing.AnyStr) fails with:
            # TypeError: Type variables cannot be used with isinstance().
            self.assertIsInstance(name, six.string_types)
            self.assertIsInstance(module, types.ModuleType)

    def test_load_entry_points_modules(self):
        register_test_entry_point()
        modules = utils.load_entry_points_modules()
        self.assertIsInstance(modules, typing.Dict)
        for name, module in six.iteritems(modules):
            # assertIsInstance(name, typing.AnyStr) fails with:
            # TypeError: Type variables cannot be used with isinstance().
            self.assertIsInstance(name, six.string_types)
            self.assertIsInstance(module, types.ModuleType)

    def test_get_all_resource_classes(self):
        classes = utils.get_resource_classes()
        self.assertIsInstance(classes, typing.List)
        for klass in classes:
            self.assertTrue(issubclass(klass, ServiceResource))

    def test_get_resource_classes(self):
        resources = ['Stacks', 'Networks']
        classes = utils.get_resource_classes(resources)
        self.assertTrue(len(classes) == 2)
        self.assertIsInstance(classes, typing.List)
        for klass in classes:
            self.assertTrue(issubclass(klass, ServiceResource))
            self.assertIn(klass.__name__, resources)

    def test_call_and_ignore_notfound(self):
        def raiser():
            raise os_exceptions.OpenStackCloudException("")

        self.assertIsNone(
            utils.call_and_ignore_exc(
                os_exceptions.OpenStackCloudException, raiser
            )
        )

        m = mock.Mock()
        utils.call_and_ignore_exc(
            os_exceptions.OpenStackCloudException, m, 42)
        self.assertEqual([mock.call(42)], m.call_args_list)
