import unittest
from domain_rollout import select_computers


class DomainRolloutTests(unittest.TestCase):
    def test_only_enabled_domain_workstations(self):
        def row(name, os='Windows 11 Pro', enabled=True, fqdn=None):
            return dict(name=name, os=os, enabled=enabled, fqdn=fqdn or name.lower()+'.volonet.local')
        snapshot = dict(domain='volonet.local', computers=[
            row('PC1'), row('DC1', 'Windows Server 2019 Standard'),
            row('OLDPC', enabled=False), row('UNKNOWN', ''),
            row('FOREIGN', fqdn='foreign.other.local'), row('../ESCAPE'),
            row('LINUX', 'Oracle Linux'), row('PC2', 'Windows 10 Enterprise')])
        self.assertEqual(['PC1', 'PC2'], [r['computer'] for r in select_computers(snapshot)])

    def test_duplicate_names_fail_instead_of_sharing_credentials(self):
        row=dict(name='PC1',os='Windows 11 Pro',enabled=True,fqdn='pc1.volonet.local')
        with self.assertRaises(ValueError):
            select_computers(dict(domain='volonet.local',computers=[row,dict(row,name='pc1')]))

    def test_missing_domain_cannot_select_arbitrary_computers(self):
        with self.assertRaises(ValueError):
            select_computers(dict(computers=[]))
