param(
    [string[]]$ComputerName = @($env:COMPUTERNAME),
    [string]$OutputDirectory = "$PSScriptRoot\data\endpoint-sessions",
    [switch]$Watch
)
# Read Windows interactive sessions using the existing Windows identity.
# No new AD account, credential storage, firewall or policy changes.
$ErrorActionPreference = 'Stop'
Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.ComponentModel;
public class CenterEKSession {
    public int id;
    public string username;
    public string domain;
    public int state;
}
public class CenterEKWTS {
    [StructLayout(LayoutKind.Sequential)] struct Info {
        public int id; public IntPtr station; public int state;
    }
    [DllImport("wtsapi32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    static extern IntPtr WTSOpenServerW(string name);
    [DllImport("wtsapi32.dll")] static extern void WTSCloseServer(IntPtr server);
    [DllImport("wtsapi32.dll", SetLastError=true)]
    static extern bool WTSEnumerateSessionsW(IntPtr server, int reserved, int version, out IntPtr data, out int count);
    [DllImport("wtsapi32.dll", SetLastError=true)]
    static extern bool WTSQuerySessionInformationW(IntPtr server, int id, int field, out IntPtr data, out int bytes);
    [DllImport("wtsapi32.dll")] static extern void WTSFreeMemory(IntPtr data);
    static string Text(IntPtr server, int id, int field) {
        IntPtr ptr; int bytes;
        if (!WTSQuerySessionInformationW(server,id,field,out ptr,out bytes))
            throw new Win32Exception(Marshal.GetLastWin32Error());
        try { return Marshal.PtrToStringUni(ptr) ?? ""; } finally { WTSFreeMemory(ptr); }
    }
    public static CenterEKSession[] Read(string name) {
        IntPtr server=WTSOpenServerW(name);
        if (server==IntPtr.Zero) throw new Win32Exception(Marshal.GetLastWin32Error());
        try {
            IntPtr ptr; int count;
            if (!WTSEnumerateSessionsW(server,0,1,out ptr,out count)) throw new Win32Exception(Marshal.GetLastWin32Error());
            try {
                List<CenterEKSession> rows=new List<CenterEKSession>();
                int size=Marshal.SizeOf(typeof(Info));
                for (int n=0;n<count;n++) {
                    Info info=(Info)Marshal.PtrToStructure(IntPtr.Add(ptr,n*size),typeof(Info));
                    string user=Text(server,info.id,5);
                    if (user.Length==0) continue;
                    rows.Add(new CenterEKSession {id=info.id,username=user,domain=Text(server,info.id,7),state=info.state});
                }
                return rows.ToArray();
            } finally { WTSFreeMemory(ptr); }
        } finally { WTSCloseServer(server); }
    }
}
'@
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
do {
    foreach ($target in $ComputerName) {
        if ($target -notmatch '^[A-Za-z0-9.-]{1,253}$') { throw 'Geçersiz bilgisayar adı' }
        $report = [ordered]@{schema=1; computer=$target; collected_at=(Get-Date).ToUniversalTime().ToString('o');
            source='Windows WTS'; address_source='DNS çözümlemesi'; ips=@(); sessions=@(); status='ok'; error=$null}
        try {
            $report.ips = @([System.Net.Dns]::GetHostAddresses($target) | Where-Object {$_.AddressFamily -eq 'InterNetwork'} | ForEach-Object {$_.IPAddressToString})
            $report.sessions = @([CenterEKWTS]::Read($target))
        } catch {
            $report.status = 'error'
            $report.error = 'Oturum sorgusu başarısız; DNS, RPC erişimi ve Windows oturum sorgulama yetkisini kontrol edin.'
        }
        $destination = Join-Path $OutputDirectory ($target+'.json')
        $temporary = $destination+'.tmp'
        $report | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $temporary -Encoding UTF8
        Move-Item -LiteralPath $temporary -Destination $destination -Force
        Write-Host "$target : $($report.status), $($report.sessions.Count) oturum"
    }
    if ($Watch) { Start-Sleep -Seconds 60 }
} while ($Watch)
