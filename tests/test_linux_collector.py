import unittest
import linux_collector
import install_linux_agent
import ast
from pathlib import Path
class LinuxResourceTests(unittest.TestCase):
 def test_available_memory_includes_reclaimable_cache(self):
  result=linux_collector.memory('MemTotal: 1048576 kB\nMemFree: 100 kB\nMemAvailable: 262144 kB\n')
  self.assertEqual(result['memory_total_gb'],1)
  self.assertEqual(result['memory_percent'],75)
 def test_cpu_does_not_double_count_guest_time(self):
  self.assertEqual(linux_collector.cpu('cpu 10 0 20 50 10 0 0 0 5 0\n'),(90,60))
 def test_invalid_memory_is_rejected(self):
  with self.assertRaises(ValueError):linux_collector.memory('MemTotal: 100 kB\nMemAvailable: 200 kB')
 def test_oracle_linux_python36_syntax_and_service_sandbox(self):
  for name in ('linux_collector.py','install_linux_agent.py'):
   ast.parse((Path(__file__).parents[1]/name).read_text(encoding='utf-8-sig'),feature_version=(3,6))
  unit=install_linux_agent.service_unit('/usr/bin/python3.6')
  for required in ('User=centerek-agent','NoNewPrivileges=true','ProtectSystem=strict','ProtectHome=true','MemoryMax=128M','CPUQuota=5%'):
   self.assertIn(required,unit)
  self.assertNotIn('oraclevolo',unit)
  with self.assertRaises(ValueError):install_linux_agent.service_unit('/usr/bin/python3\nExecStart=/bad')
if __name__=='__main__':unittest.main()
