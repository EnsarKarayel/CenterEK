# Linux resource collector — preparation

linux_collector.py reads /proc memory/CPU counters, global IPv4 adapters and
capacity of local xfs/ext/btrfs mounts. It does not query Oracle Database, traverse
data directories, install packages, change a firewall or open an inbound port.

Local parser tests pass. Real execution on Oracle Linux 8.10, Python availability,
per-machine enrollment, office CA trust, systemd installation and end-to-end
Azure dashboard acceptance remain pending. This file is not installed anywhere.
Linux sessions are not collected; the Windows WTS agent remains responsible for
interactive Windows user-to-computer mapping. Before rollout, preserve platform
metadata in the receiving registry rather than labelling Linux reports Windows.

Use a dedicated endpoint enrollment for VOLO-PRODDB, never a site/FortiGate/admin
credential. A production service should run unprivileged with its token file
restricted to mode 600, verified HTTPS and redirects disabled. A service unit and
safe installer still need implementation after checking the target interpreter.
