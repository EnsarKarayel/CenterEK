# Windows 11 native acceptance — 2026-11-19

The tested artifact came from merged main commit `157972666c1ea5727fb7a5a33ee9490852f60878`, CI run `44294883818`. Its archive and outer setup hashes were checked before testing. These results concern the unsigned 0.9.3 preview, not a commercial release.

## Clean installation passed

`windows11-clean.json` records a real Windows 11 Enterprise build 26100 Sandbox guest without Python. Installation, trusted local HTTPS/login, SYSTEM server/endpoint tasks, endpoint receipt, Windows application registration, data-preserving uninstall and restoration with the original account passed. Networking and clipboard sharing were disabled; only a dedicated report folder was writable from the guest.

The inner executable SHA256 is `ea25e3d9fdd9c497f59d6ad1bc8884f0e77ab77706ce78224c99812ae6eee3e9`; the outer setup is `a634f2072281b4560b65fe9682e90fc047b33985c475a7b4516f812550c87600`. This was automated installation through the packaged entry point; outer setup UI/UAC interaction remains pending.

## Guest reboot: startup passed, endpoint acceptance blocked

Windows 11 Sandbox supports [restarts initiated inside the guest](https://learn.microsoft.com/en-us/windows/security/application-security/application-isolation/windows-sandbox/). Earlier project notes treating all Sandbox reboots as impossible were too broad. Closing a Sandbox still discards it; restarting it internally is different.

The same Sandbox session was restarted through Microsoft's CLI. The Windows boot time changed from `11:10:09Z` to `11:20:20Z`. Installation UUID and inner executable hash were preserved. Both SYSTEM startup tasks ran, HTTPS login and PWA assets loaded, and the anonymous API remained blocked.

In this observed Sandbox run, the Windows computer name changed during reboot. The endpoint collector consequently rejected its old computer-bound enrollment with `Wrong endpoint computer registration`. No new authenticated post-boot RAM/disk report was received. The production identity guard was retained; no agent was re-enrolled and no task was manually restarted to manufacture a pass.

`windows11-sandbox-reboot.json` therefore records `ok:false` and `reboot_test:blocked_environment_identity_changed`. It is **not** a passed end-to-end reboot acceptance. A stable-identity VM is needed to finish that check; a full persistent-VM power cycle and Windows Server acceptance remain untested.

## ISO and host scope

The downloaded Windows Enterprise evaluation ISO (build 26300) was mounted read-only for inspection. Its x64 boot and installation image files were readable, and `setup.exe` had a valid Microsoft Authenticode signature. The ISO SHA256 was recorded locally. This ISO was **not** the operating system image used for the completed Sandbox test; no installation from that ISO is claimed.

The user's host and office machines were not rebooted by these tests. Local Hyper-V VM management components remain unavailable while Windows reports pending component servicing. No sale-ready approval, trusted publisher signature or commercial-license acceptance was created.
