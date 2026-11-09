import unittest
import linux_collector
import install_linux_agent
import ast
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
class LinuxResourceTests(unittest.TestCase):
 def test_available_memory_includes_reclaimable_cache(self):
  result=linux_collector.memory('MemTotal: 1048576 kB\nMemFree: 100 kB\nMemAvailable: 262144 kB\n')
  self.assertEqual(result['memory_total_gb'],1)
  self.assertEqual(result['memory_percent'],75)
 def test_cpu_does_not_double_count_guest_time(self):
  self.assertEqual(linux_collector.cpu('cpu 10 0 20 50 10 0 0 0 5 0\n'),(90,60))
 def test_invalid_memory_is_rejected(self):
  with self.assertRaises(ValueError):linux_collector.memory('MemTotal: 100 kB\nMemAvailable: 200 kB')
 def test_local_mounts_only_and_full_disk_does_not_block_report(self):
  fixture={'/proc/meminfo':'MemTotal: 1048576 kB\nMemAvailable: 262144 kB\n',
   '/proc/stat':'cpu 10 0 20 50 10 0 0 0 5 0\n',
   '/proc/self/mountinfo':'1 0 8:1 / / rw - xfs /dev/root rw\n2 0 8:1 /usr /usr ro - xfs /dev/root ro\n3 0 8:2 / /u01 rw - xfs /dev/data rw\n4 0 0:9 / /remote rw - nfs server:/data rw\n'}
  with patch.object(linux_collector.socket,'gethostname',return_value='volo-proddb'), \
       patch.object(linux_collector.subprocess,'check_output',return_value='[]'), \
       patch.object(linux_collector.time,'sleep'), \
       patch.object(Path,'read_text',lambda path:fixture[path.as_posix()]), \
       patch.object(linux_collector.os.path,'isdir',return_value=True), \
       patch.object(linux_collector.os,'statvfs',create=True,return_value=SimpleNamespace(f_blocks=262144,f_frsize=4096,f_bavail=-1)) as stat:
   report=linux_collector.collect('VOLO-PRODDB')
  self.assertEqual([v['name'] for v in report['volumes']],['/','/u01'])
  self.assertEqual(stat.call_count,2)
  self.assertEqual(report['volumes'][0]['free_gb'],0)
  self.assertEqual(report['sessions'],[])
  self.assertEqual(report['resources']['memory_percent'],75)
 def test_oracle_linux_python36_syntax_and_service_sandbox(self):
  for name in ('linux_collector.py','install_linux_agent.py'):
   ast.parse((Path(__file__).parents[1]/name).read_text(encoding='utf-8-sig'),feature_version=(3,6))
  unit=install_linux_agent.service_unit('/usr/bin/python3.6')
  for required in ('User=centerek-agent','NoNewPrivileges=true','ProtectSystem=strict','ProtectHome=true','MemoryMax=128M','CPUQuota=5%'):
   self.assertIn(required,unit)
  self.assertNotIn('oraclevolo',unit)
  with self.assertRaises(ValueError):install_linux_agent.service_unit('/usr/bin/python3\nExecStart=/bad')
if __name__=='__main__':unittest.main()
