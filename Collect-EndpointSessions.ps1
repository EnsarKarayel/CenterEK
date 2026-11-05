param(
    [string[]]$ComputerName = @($env:COMPUTERNAME),
    [string]$OutputDirectory = "$PSScriptRoot\data\endpoint-sessions",
    [string]$AgentConfig,
    [switch]$Watch
)
# Read Windows interactive sessions using the existing Windows identity.
# No new AD account, credential storage, firewall or policy changes.
$ErrorActionPreference = 'Stop'
if ($AgentConfig) {
    . "$PSScriptRoot\Send-Report.ps1"
    $agent = Get-Content -LiteralPath $AgentConfig -Raw | ConvertFrom-Json
    if ($agent.kind -ne 'endpoint' -or $agent.computer.Split('.')[0] -ine $env:COMPUTERNAME) { throw 'Yanlış uç bilgisayar kaydı' }
    $ComputerName = @($agent.computer)
}
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
public class CenterEKResources {
    [StructLayout(LayoutKind.Sequential)] struct Memory {
        public uint length; public uint load; public ulong total; public ulong available;
        public ulong totalPage; public ulong availablePage; public ulong totalVirtual; public ulong availableVirtual; public ulong extended;
    }
    [DllImport("kernel32.dll", SetLastError=true)] static extern bool GlobalMemoryStatusEx(ref Memory memory);
    [DllImport("kernel32.dll", SetLastError=true)] static extern bool GetSystemTimes(out long idle,out long kernel,out long user);
    static long previousIdle,previousTotal;
    public static Dictionary<string,object> Read() {
        Memory m=new Memory(); m.length=(uint)Marshal.SizeOf(typeof(Memory));
        if(!GlobalMemoryStatusEx(ref m)) throw new Win32Exception(Marshal.GetLastWin32Error());
        Dictionary<string,object> values=new Dictionary<string,object>();
        values["memory_total_gb"]=Math.Round(m.total/1073741824.0,2);
        values["memory_used_gb"]=Math.Round((m.total-m.available)/1073741824.0,2);
        values["memory_percent"]=Math.Round((m.total-m.available)*100.0/m.total,1);
        values["cpu_percent"]=null;
        long idle,kernel,user;
        if(GetSystemTimes(out idle,out kernel,out user)) {
            long total=kernel+user, delta=total-previousTotal;
            if(previousTotal>0 && delta>0) values["cpu_percent"]=Math.Round(Math.Max(0,Math.Min(100,100.0*(delta-(idle-previousIdle))/delta)),1);
            previousIdle=idle;previousTotal=total;
        }
        return values;
    }
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
            source='Windows WTS'; address_source='DNS çözümlemesi'; ips=@(); sessions=@(); status='ok'; error=$null;
            resources=@{}; interfaces=@(); primary_ip=$null}
        try {
            $report.ips = @([System.Net.Dns]::GetHostAddresses($target) | Where-Object {$_.AddressFamily -eq 'InterNetwork'} | ForEach-Object {$_.IPAddressToString})
            $report.sessions = @([CenterEKWTS]::Read($target))
            try { if ($target.Split('.')[0] -ieq $env:COMPUTERNAME) {
                $report.ips=@()
                foreach ($nic in [Net.NetworkInformation.NetworkInterface]::GetAllNetworkInterfaces()) {
                    if ($nic.OperationalStatus -ne 'Up' -or $nic.NetworkInterfaceType -eq 'Loopback') { continue }
                    $properties=$nic.GetIPProperties()
                    foreach ($address in $properties.UnicastAddresses) {
                        $ip=$address.Address.IPAddressToString
                        if ($address.Address.AddressFamily -ne 'InterNetwork' -or $ip -like '169.254.*') { continue }
                        $report.ips += $ip
                        $report.interfaces += [ordered]@{name=$nic.Name;ip=$ip}
                        if (-not $report.primary_ip -and @($properties.GatewayAddresses | Where-Object { $_.Address.ToString() -ne '0.0.0.0' }).Count) { $report.primary_ip=$ip }
                    }
                }
                $report.address_source='Yerel ağ kartları'
                $report.resources=[CenterEKResources]::Read()
            } } catch { Write-Warning 'Ek CPU/RAM veya ağ kartı ölçümü alınamadı; oturum verisi korunuyor.' }
        } catch {
            $report.status = 'error'
            $report.error = 'Oturum sorgusu başarısız; DNS, RPC erişimi ve Windows oturum sorgulama yetkisini kontrol edin.'
        }
        $destination = Join-Path $OutputDirectory ($target+'.json')
        $temporary = $destination+'.tmp'
        $report | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $temporary -Encoding UTF8
        Move-Item -LiteralPath $temporary -Destination $destination -Force
        Write-Host "$target : $($report.status), $($report.sessions.Count) oturum"
        if ($AgentConfig) {
            try { Send-CenterEKReport -AgentConfig $AgentConfig -ReportFile $destination }
            catch { Write-Warning 'Rapor gönderilemedi. Ağ, HTTPS güveni ve ajan kaydını kontrol edin; sonraki turda tekrar denenecek.' }
        }
    }
    if ($Watch) { Start-Sleep -Seconds 60 }
} while ($Watch)
