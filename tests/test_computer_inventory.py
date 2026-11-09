import unittest
import endpoints
class ComputerInventoryTests(unittest.TestCase):
 def directory(self):return {'domain':'volonet.local','stale':False,'computers':[{'name':'PC01','fqdn':'pc01.volonet.local','enabled':True},{'name':'PC02','fqdn':'pc02.volonet.local','enabled':True}],'clients':[{'hostname':'pc01.volonet.local','ip':'192.168.1.20','source':'DNS kaydı'},{'hostname':'pc02.volonet.local','ip':'192.168.1.20','source':'DNS kaydı'}]}
 def test_all_ad_computers_visible_without_agents(self):
  rows=endpoints.computer_inventory(self.directory(),[],[])
  self.assertEqual(len(rows),2)
  self.assertEqual(rows[0]['ips'],['192.168.1.20'])
  self.assertEqual(rows[0]['report_status'],'missing')
  self.assertEqual(rows[0]['users'],[])
 def test_user_is_matched_to_fresh_computer_never_shared_dns_ip(self):
  reports=[{'computer':'PC01','stale':False,'status':'ok','ips':['192.168.1.30'],'checked':'now'}]
  sessions=[{'computer':'PC01','stale':False,'state':'active','username':'alice','domain':'VOLONET','ad_match':True}]
  rows=endpoints.computer_inventory(self.directory(),reports,sessions)
  self.assertEqual(rows[0]['ips'],['192.168.1.30'])
  self.assertEqual(rows[0]['users'][0]['username'],'alice')
  self.assertEqual(rows[1]['users'],[])
 def test_stale_or_ambiguous_reports_cannot_claim_current_user(self):
  report={'computer':'PC01','stale':True,'status':'ok','ips':['192.168.1.30']}
  sessions=[{'computer':'PC01','stale':True,'state':'active','username':'alice','domain':'VOLONET'}]
  self.assertEqual(endpoints.computer_inventory(self.directory(),[report],sessions)[0]['users'],[])
  report['stale']=False;sessions[0]['stale']=False
  rows=endpoints.computer_inventory(self.directory(),[report,dict(report)],sessions)
  self.assertEqual(rows[0]['report_status'],'ambiguous');self.assertEqual(rows[0]['users'],[])
if __name__=='__main__':unittest.main()
