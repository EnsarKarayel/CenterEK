# Windows 11 native acceptance — 2026-11-17

These are observed results from disposable Windows Sandbox guests, not mocked Windows task APIs. The image was Windows 11 Enterprise build 26100 without an installed Python runtime. Host networking and clipboard access were disabled; installer input was read-only, with only a dedicated report folder writable.

- `windows11-clean.json`: real 0.9.2 installation, HTTPS/login, SYSTEM server and endpoint tasks, received endpoint telemetry, Windows Apps registration, data-preserving uninstall and restoration with the original account all passed.
- `windows11-upgrade-rollback.json`: real 0.9.1 installation, 0.9.1 → 0.9.2 upgrade, 0.9.2 → 0.9.1 rollback, then uninstall/restoration all passed. Account login and installation identity were checked across the version changes. The initial-version field remains 0.9.1; separate fields record the observed upgraded and rolled-back versions.

The reports identify the exact inner executable hashes. These are unsigned preview packages; no production signing identity or commercial license approval is asserted. `reboot_test`, `uac_interaction` and `outer_setup_ui` remain `pending`. No persistent VM reboot, Windows Server, or publicly trusted commercial signing acceptance is claimed.

Earlier native runs found two defects that were fixed before these reports: using a long DNS hostname instead of Windows NetBIOS identity for enrollment, and Windows PowerShell 5.1 nesting a top-level task-state JSON array. Ownership checks were retained. The corrected helper was also tested with empty, single and multiple task states under Windows PowerShell.

Generated credentials and agent secrets are not included. Raw diagnostic logs remain outside Git under ignored `data/`.
