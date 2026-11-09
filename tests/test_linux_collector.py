import unittest
import linux_collector
class LinuxResourceTests(unittest.TestCase):
 def test_available_memory_includes_reclaimable_cache(self):
  result=linux_collector.memory('MemTotal: 1048576 kB\nMemFree: 100 kB\nMemAvailable: 262144 kB\n')
  self.assertEqual(result['memory_total_gb'],1)
  self.assertEqual(result['memory_percent'],75)
 def test_cpu_does_not_double_count_guest_time(self):
  self.assertEqual(linux_collector.cpu('cpu 10 0 20 50 10 0 0 0 5 0\n'),(90,60))
 def test_invalid_memory_is_rejected(self):
  with self.assertRaises(ValueError):linux_collector.memory('MemTotal: 100 kB\nMemAvailable: 200 kB')
if __name__=='__main__':unittest.main()
