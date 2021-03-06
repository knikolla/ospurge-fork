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
import importlib
import logging
import os
import pkgutil
import re

import pkg_resources

from ospurge.resources import base


ENTRY_POINTS_NAME = 'ospurge_resources'


def load_ospurge_resource_modules():
    """Import all the modules in the `resources` package."""
    modules = {}
    iter_modules = pkgutil.iter_modules(
        [os.path.join(os.path.dirname(__file__), 'resources')],
        prefix='ospurge.resources.'
    )
    for (_, name, ispkg) in iter_modules:
        if not ispkg:
            modules[name] = importlib.import_module(name)
    return modules


def load_entry_points_modules(name=ENTRY_POINTS_NAME):
    """Import all modules in the `name` entry point."""
    entry_points = {}
    for entry_point in pkg_resources.iter_entry_points(name):
        entry_points[entry_point.name] = entry_point.load()
    return entry_points


def get_resource_classes(resources=None):
    """
    Load all ospurge resource and entry point modules and return all the
    subclasses of the `ServiceResource` ABC that match the `resources` arg.

    This way we can easily extend OSPurge by just adding a new file in the
    `resources` dir or a package with `ENTRY_POINTS_NAME` entry point.
    """
    load_entry_points_modules()
    load_ospurge_resource_modules()

    all_classes = base.ServiceResource.__subclasses__()

    # If we don't want to filter out which classes to return, use a global
    # wildcard regex.
    if not resources:
        regex = re.compile(".*")
    # Otherwise, build a regex by concatenation.
    else:
        regex = re.compile('|'.join(resources))

    return [c for c in all_classes if regex.match(c.__name__)]


def call_and_ignore_exc(exc, f, *args):
    try:
        f(*args)
    except exc as e:
        logging.debug("The following exception was ignored: %r", e)
