import collections

import tconnectsync.nightscout

class NightscoutApi(tconnectsync.nightscout.NightscoutApi):
    def __init__(self):
        self.url = 'invalid://'
        self.secret = 'invalid'

        self.uploaded_entries = collections.defaultdict(list)
        self.deleted_entries = []
        self.put_entries = collections.defaultdict(list)

    def upload_entry(self, ns_format, entity='treatments'):
        self.uploaded_entries[entity].append(ns_format)

    def delete_entry(self, ns_path):
        self.deleted_entries.append(ns_path)

    def put_entry(self, ns_format, entity):
        self.put_entries[entity].append(ns_format)

    def last_uploaded_entry(self, eventType):
        raise NotImplementedError

    def last_uploaded_activity(self, activityType):
        raise NotImplementedError

    def api_status(self):
        raise NotImplementedError

