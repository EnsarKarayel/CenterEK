import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import monitor
import network_discovery


class NetworkDiscoveryTests(unittest.TestCase):
    def test_networks_deduplicate_wifi_ethernet_and_skip_virtual_public_and_large(self):
        rows=[{'ip':'192.168.1.10','mask':'255.255.252.0','gateway':'192.168.1.1','type':'Ethernet','description':'Ethernet'},
              {'ip':'192.168.2.10','mask':'255.255.252.0','gateway':'192.168.1.1','type':'Wireless80211','description':'Wi-Fi'},
              {'ip':'172.31.0.1','mask':'255.255.240.0','gateway':'172.31.0.2','type':'Ethernet','description':'Hyper-V Virtual'},
              {'ip':'8.8.8.8','mask':'255.255.255.0','gateway':'8.8.8.1','type':'Ethernet'},
              {'ip':'10.1.1.5','mask':'255.0.0.0','gateway':'10.1.1.1','type':'Ethernet'}]
        networks,skipped=network_discovery.select_networks(rows)
        self.assertEqual([str(n) for n in networks],['192.168.0.0/22'])
        self.assertEqual(len(skipped),1)

    def test_auto_add_preserves_existing_device_and_rejects_public(self):
        config={'interval':30,'threshold':3,'timeout':2,'devices':[
            {'id':'known','name':'Keep my name','host':'192.168.1.1','kind':'Firewall','method':'tcp','port':4443}]}
        rows=[{'host':'192.168.1.1','icmp':True,'open_tcp_ports':[]},
              {'host':'192.168.1.20','icmp':False,'open_tcp_ports':[443]},
              {'host':'8.8.8.8','icmp':True,'open_tcp_ports':[]}]
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'config.local.json';path.write_text(json.dumps(config))
            added=network_discovery.add_discovered(config,rows,path,monitor.validate)
            self.assertEqual(added,1)
            self.assertEqual(config['devices'][0]['name'],'Keep my name')
            self.assertEqual(config['devices'][1]['port'],443)
            self.assertEqual(config['devices'][1]['kind'],'Diğer')
            self.assertEqual(network_discovery.add_discovered(config,rows,path,monitor.validate),0)
            store=monitor.Store(':memory:')
            try:
                store.record(config['devices'][1]['id'],True,1,None,3)
                with patch.object(monitor,'ROOT',Path(temporary)):
                    inventory=store.inventory(config)
                self.assertEqual(inventory['clients'][0]['ip'],'192.168.1.20')
                self.assertTrue(inventory['clients'][0]['online'])
                self.assertIsNone(inventory['clients'][0]['os'])
            finally:
                store.db.close()
