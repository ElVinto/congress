# Copyright (c) 2014 VMware, Inc. All rights reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#
import glanceclient.v2.client as glclient
import keystoneclient.v2_0.client as ksclient

from congress.datasources import datasource_driver
from congress.datasources import datasource_utils
from congress.openstack.common import log as logging

LOG = logging.getLogger(__name__)


def d6service(name, keys, inbox, datapath, args):
    """This method is called by d6cage to create a dataservice instance."""
    return GlanceV2Driver(name, keys, inbox, datapath, args)


class GlanceV2Driver(datasource_driver.DataSourceDriver):

    IMAGES = "images"
    TAGS = "tags"

    value_trans = {'translation-type': 'VALUE'}
    images_translator = {
        'translation-type': 'HDICT',
        'table-name': IMAGES,
        'selector-type': 'DICT_SELECTOR',
        'field-translators':
            ({'fieldname': 'id', 'translator': value_trans},
             {'fieldname': 'status', 'translator': value_trans},
             {'fieldname': 'name', 'translator': value_trans},
             {'fieldname': 'container_format', 'translator': value_trans},
             {'fieldname': 'created_at', 'translator': value_trans},
             {'fieldname': 'updated_at', 'translator': value_trans},
             {'fieldname': 'disk_format', 'translator': value_trans},
             {'fieldname': 'owner', 'translator': value_trans},
             {'fieldname': 'protected', 'translator': value_trans},
             {'fieldname': 'min_ram', 'translator': value_trans},
             {'fieldname': 'min_disk', 'translator': value_trans},
             {'fieldname': 'checksum', 'translator': value_trans},
             {'fieldname': 'size', 'translator': value_trans},
             {'fieldname': 'file', 'translator': value_trans},
             {'fieldname': 'kernel_id', 'translator': value_trans},
             {'fieldname': 'ramdisk_id', 'translator': value_trans},
             {'fieldname': 'schema', 'translator': value_trans},
             {'fieldname': 'visibility', 'translator': value_trans},
             {'fieldname': 'tags',
              'translator': {'translation-type': 'LIST',
                             'table-name': 'tags',
                             'val-col': 'tag',
                             'parent-key': 'id',
                             'parent-col-name': 'image_id',
                             'translator': value_trans}})}

    TRANSLATORS = [images_translator]

    def __init__(self, name='', keys='', inbox=None, datapath=None, args=None):
        super(GlanceV2Driver, self).__init__(name, keys, inbox, datapath, args)
        self._initialize_tables()
        self.creds = args

        keystone = ksclient.Client(**self.creds)
        glance_endpoint = keystone.service_catalog.url_for(
            service_type='image', endpoint_type='publicURL')
        self.glance = glclient.Client(glance_endpoint,
                                      token=keystone.auth_token)
        self.initialized = True

    @staticmethod
    def get_datasource_info():
        result = {}
        result['id'] = 'glancev2'
        result['description'] = ('Datasource driver that interfaces with '
                                 'OpenStack Images aka Glance.')
        result['config'] = datasource_utils.get_openstack_required_config()
        result['secret'] = ['password']
        return result

    def update_from_datasource(self):
        """Called when it is time to pull new data from this datasource.

        Sets self.state[tablename] = <set of tuples of strings/numbers>
        for every tablename exported by this datasource.
        """
        LOG.debug("Grabbing Glance Images")
        images = {'images': []}
        # TODO(zhenzanz): this is a workaround. The glance client should
        # handle 401 error.
        try:
            for image in self.glance.images.list():
                images['images'].append(image)
            self._translate_images(images)
        except Exception as e:
            if e.code == 401:
                keystone = ksclient.Client(**self.creds)
                self.glance.http_client.auth_token = keystone.auth_token
            else:
                raise e

    def _translate_images(self, obj):
        """Translate the images represented by OBJ into tables.

        Assigns self.state[tablename] for all those TABLENAMEs
        generated from OBJ: IMAGES
        """
        LOG.debug("IMAGES: %s", str(dict(obj)))
        row_data = GlanceV2Driver.convert_objs(
            obj['images'], GlanceV2Driver.images_translator)
        self._initialize_tables()
        for table, row in row_data:
            self.state[table].add(row)

    def _initialize_tables(self):
        self.state[self.IMAGES] = set()
        self.state[self.TAGS] = set()
