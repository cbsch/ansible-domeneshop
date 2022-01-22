#!/usr/bin/python3
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.json_utils import json
from domeneshop import Client
import os

import yaml

DOCUMENTATION = """
---
module: dns.py
short_description: Update DNS records on Domeneshop
description:
  - Update DNS records on Domeneshop
options:
  domain:
    description:
      - domain to create / update records for
  host:
    description:
      - the dns record to create / update
  type:
    description:
      - the type to set for the record (A,AAAA,CNAME, etc.)
  data:
    description:
      - the value the to set for the record, for example an IPv4 address for A or another DNS name for CNAME
  ttl:
    description:
      - the time to live (ttl) to set on the record in seconds
  usecache:
    description:
      - will save record data for a single run in /tmp/ansible_domeneshop_cache.json, speeding up execution
  apikey:
    description:
      - Domeneshop API key
  apisecret:
    description:
      - Domeneshop API secret
"""

CACHEFILE = '/tmp/ansible_domeneshop_cache.json'


VALID_TYPES = [
    "A",
    "AAAA",
    "CNAME",
    "ANAME",
    "TLSA",
    "MX",
    "SRV",
    "DS",
    "CAA",
    "NS",
    "TXT",
]

def log(msg):
    True
    # LOGFILE = '/tmp/log_ansible'
    # with open(LOGFILE, "a") as file:
    #     file.write(msg + "\n")

class Domain:
    def __init__(self, module: AnsibleModule):
        self.module = module
        self.domain = module.params['domain']
        self.record = None
        self.records = None

        # To avoid a lot of uneccessary http requests we cache the results for a single play.
        # The pid of a a "play" is our great, great grandparents' pid.
        self.play_pid = pnid(os.getpid(), 4)

        self.wants = {}
        self.wants['host'] = module.params['host']
        self.wants['ttl'] = module.params['ttl']
        self.wants['type'] = module.params['type']
        self.wants['data'] = module.params['data']

        apikey = module.params['apikey'] if module.params['apikey'] else os.environ['DOMENESHOP_APIKEY']
        apisecret = module.params['apisecret'] if module.params['apisecret'] else os.environ['DOMENESHOP_APISECRET']

        self.client = Client(apikey, apisecret)

    def get_cached_data(self):
        if (os.path.exists(CACHEFILE)):
            # Cache exists
            try:
                cache = json.load(open(CACHEFILE, 'r'))
            except Exception:
                cache = None
            if cache and cache['play_pid'] == self.play_pid:
                # Cache exists and has been refreshed this play
                if not cache['domains'][self.domain]:
                    # Cache does not include the current domain
                    # Update it and write to file
                    cache['domains'][self.domain] = self.get_domain_data()
                    log('Write cache (update) host: {0} record: {1}'.
                        format(self.wants['host'], self.wants['type']))
                    self.write_cache(cache)
            else:
                # Cache exists, but is for an earlier play or failed to open, refresh it
                log('Create cache (invalid) host: {0} record: {1}'.
                    format(self.wants['host'], self.wants['type']))
                cache = self.create_cache()
        else:
            # Cache does not exist, create it
            log('Create cache (didnt exist) host: {0} record: {1}'.
                format(self.wants['host'], self.wants['type']))
            cache = self.create_cache()

        self.domain_id = cache['domains'][self.domain]['domain']['id']
        self.records = cache['domains'][self.domain]['records']

        return True

    def get_noncached_data(self):
        data = self.get_domain_data()
        self.domain_id = data["domain"]["id"]
        self.records = data["records"]

        return True

    def get_domain_data(self):
        domains = self.client.get_domains()
        domain = domains[next(i for i, e in enumerate(domains) if e["domain"] == self.domain)]
        records = self.client.get_records(domain["id"])

        return dict(
            domain = domain,
            records = records
        )

    def write_cache(self, cache: dict):
        with os.fdopen(os.open(CACHEFILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), 'w') as file:
            json.dump(cache, file)

    def create_cache(self):
        domain_data = {}
        domain_data[self.domain] = self.get_domain_data()

        cache = dict(
            play_pid = self.play_pid,
            domains = domain_data
        )

        self.write_cache(cache)

        return cache

    def get_record(self):
        def find_dns(record):
            # Find DNS needs to be able to handle conflicts - can't have CNAME and A or CNAME and AAAA
            if record['host'] == self.wants['host']:
                if self.wants['type'] == 'NS' and self.wants['data'] != record['data']:
                    # There can be multiple NS records on a host, so we cannot target a single
                    # NS record to change its data. We can only add or remove
                    return False
                if self.wants['type'] == 'NS' and self.wants['data'] == record['data']:
                    # If we target a NS a record with type and the data matches we can
                    # change other parameters like TTL
                    return True
                if record['type'] == self.wants['type']:
                    return True
                if record['type'] == 'CNAME' or self.wants['type'] == 'CNAME':
                    # If either before or after has type CNAME we return a match.
                    # If wants is CNAME and there are multiple records for the host
                    # the attempted modification will most likely fail.
                    return True
            return False

        record = next(filter(find_dns, self.records), False)
        if not record:
            return

        self.record_id = record['id']
        del record['id']
        self.record = record

    def create_record(self):
        if not self.module.check_mode:
            self.client.create_record(self.domain_id, self.wants)

        self.module.exit_json(
            changed='Create DNS record "{0}"'.format(self.wants['host']),
            data = self.wants
        )

    def dns_record_differs(self):
        if self.record != self.wants:
            return True
        else:
            return False

    def update_dns_record(self):
        result = {}
        result['changed'] = True
        result['diff'] = dict(
            before=yaml.safe_dump(self.record),
            after=yaml.safe_dump(self.wants)
        )

        if not self.module.check_mode:
            self.client.modify_record(self.domain_id, self.record_id, self.wants)

        self.module.exit_json(**result)

    def delete_record(self):
        if not self.module.check_mode:
            self.client.delete_record(self.domain_id, self.record_id)

        self.module.exit_json(
            changed='removed "{0}" record for host "{1}"'.format(self.wants['type'], self.wants['host']),
            diff=dict(
                state = 'absent'
            )
        )


def pnid(pid = None, N = 1):
    "Get parent (if N==1), grandparent (if N==2), ... of pid (or self if not given)"
    if pid is None:
        pid = "self"

    while N > 0:
        filename = "/proc/%s/status" % pid
        with open(filename, "r") as fp:
            for line in fp:
                if line.startswith("PPid:"):
                    _, _, pid = line.rpartition("\t")
                    pid = pid.rstrip()  # drop the '\n' at end
                    break
        N -= 1

    return int(pid)  # let it fail through


def main():
    module = AnsibleModule(
        argument_spec=dict(
            domain = dict(type='str', required=True),
            host = dict(type='str', required=True),
            ttl = dict(type='int'),
            type = dict(type='str', required=True, choices=VALID_TYPES),
            state = dict(type='str', choices=['present', 'absent'], default='present'),
            data = dict(type='str', required=True),
            apikey = dict(type='str'),
            apisecret = dict(type='str', no_log=True),
            usecache = dict(type='bool')
        ),
        supports_check_mode=True
    )

    domain = Domain(module)

    if module.params["usecache"]:
        success = domain.get_cached_data()
    else:
        success = domain.get_noncached_data()

    if not success:
        module.fail_json(msg='Could not find domain')

    domain.get_record()
    if module.params['state'] == 'present':
        if not domain.record:
            domain.create_record()
        if domain.dns_record_differs():
            domain.update_dns_record()
    else:
        if domain.record:
            domain.delete_record()

    module.exit_json(
        changed = False,
        data = domain.record
    )


if __name__ == '__main__':
    main()
