param([string]$Source=$PSScriptRoot,[string]$ShareName='CenterEKDeploy$')
$ErrorActionPreference='Stop'
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
if(-not (New-Object Security.Principal.WindowsPrincipal($identity)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Run as domain administrator on VOLO'}
Import-Module ActiveDirectory
$domain=Get-ADDomain
$manifest=Get-Content -LiteralPath (Join-Path $Source 'rollout.local.json') -Raw|ConvertFrom-Json
if($manifest.schema -ne 1 -or $manifest.domain -ine $domain.DNSRoot){throw 'AD domain does not match the prepared manifest'}
if($ShareName -notmatch '^[A-Za-z0-9-]+\$$'){throw 'Use a dedicated hidden share name'}
$target=Join-Path $env:ProgramData 'CenterEK-DomainDistribution'
if((Test-Path -LiteralPath $target) -or (Get-SmbShare -Name $ShareName -ErrorAction SilentlyContinue)){throw 'Existing distribution preserved; do not overwrite or reset its ACLs'}
if((Get-Item -Force -LiteralPath $env:ProgramData).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Unsafe ProgramData path'}
if(@(Get-ChildItem -LiteralPath $Source -Recurse -Force | Where-Object {$_.Attributes -band [IO.FileAttributes]::ReparsePoint}).Count){throw 'Reparse-point source rejected'}
$computersSid=$domain.DomainSID.Value+'-515'
$adminSid='S-1-5-32-544'
function Set-ProtectedDirectory([string]$Path,[string]$ReadSid,[bool]$InheritRead=$true){
    $acl=New-Object Security.AccessControl.DirectorySecurity
    $acl.SetAccessRuleProtection($true,$false)
    $acl.SetOwner((New-Object Security.Principal.SecurityIdentifier($adminSid)))
    foreach($sid in @('S-1-5-18',$adminSid)){
        $acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule((New-Object Security.Principal.SecurityIdentifier($sid)),'FullControl','ContainerInherit,ObjectInherit','None','Allow')))
    }
    if($ReadSid){
        $inherit=if($InheritRead){'ContainerInherit,ObjectInherit'}else{'None'}
        $acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule((New-Object Security.Principal.SecurityIdentifier($ReadSid)),'ReadAndExecute',$inherit,'None','Allow')))
    }
    Set-Acl -LiteralPath $Path -AclObject $acl
}
$files=@('Collect-EndpointSessions.ps1','Send-Report.ps1','Setup-Agent.ps1','Install-SystemTask.ps1','Run-SystemTask.ps1','Install-EndpointPilot.ps1','enrollment.local.json','panel-ca.pem')
$plan=@()
$seen=@{}
foreach($row in $manifest.computers){
    $name=[string]$row.computer
    # Case-sensitive ASCII validation avoids Turkish IgnoreCase I/i folding.
    if($name -cnotmatch '^[A-Z0-9][A-Z0-9-]{0,14}$' -or $seen.ContainsKey($name)){throw 'Invalid or duplicate manifest computer'}
    $seen[$name]=$true
    $folder=Join-Path $Source ('packages\'+$name)
    if(-not(Test-Path -LiteralPath $folder)){continue}
    $computer=Get-ADComputer -Identity $name -Properties Enabled,OperatingSystem,DNSHostName
    if(-not $computer.Enabled -or $computer.OperatingSystem -notmatch '^Windows (8|10|11)(\b|\.)' -or $computer.OperatingSystem -match 'Server'){throw ('Computer is not an enabled workstation: '+$name)}
    if($computer.DNSHostName -ine ($name+'.'+$domain.DNSRoot)){throw 'Computer domain mismatch'}
    foreach($file in $files){if(-not(Test-Path -LiteralPath (Join-Path $folder $file))){throw ('Missing component: '+$name+'/'+$file)}}
    $record=Get-Content -LiteralPath (Join-Path $folder 'enrollment.local.json') -Raw|ConvertFrom-Json
    if($record.kind -ne 'endpoint' -or $record.computer -ine $name){throw 'Enrollment computer mismatch'}
    $plan+=@{Name=$name;Source=$folder;Sid=$computer.SID.Value}
}
if(-not $plan.Count){throw 'No new workstation packages to publish'}
# Validate all accounts and inputs before publishing any share.
New-Item -ItemType Directory -Path $target|Out-Null
Set-ProtectedDirectory $target $computersSid $false
$packages=Join-Path $target 'packages'
New-Item -ItemType Directory -Path $packages|Out-Null
Set-ProtectedDirectory $packages $computersSid $false
foreach($item in $plan){
    $folder=Join-Path $packages $item.Name
    New-Item -ItemType Directory -Path $folder|Out-Null
    Set-ProtectedDirectory $folder $item.Sid
    foreach($file in $files){Copy-Item -LiteralPath (Join-Path $item.Source $file) -Destination (Join-Path $folder $file)}
    & icacls.exe (Join-Path $folder '*') /reset /T /C|Out-Null
    if($LASTEXITCODE){throw 'Machine-specific package ACL failed; share was not created'}
    & icacls.exe $folder /setowner '*S-1-5-32-544' /T /C|Out-Null
    if($LASTEXITCODE){throw 'Package ownership failed; share was not created'}
}
$startup=Join-Path $target 'Start-DomainEndpoint.ps1'
Copy-Item -LiteralPath (Join-Path $Source 'Start-DomainEndpoint.ps1') -Destination $startup
& icacls.exe $startup /reset|Out-Null
if($LASTEXITCODE){throw 'Startup file ACL failed'}
$acl=Get-Acl -LiteralPath $startup
$acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule((New-Object Security.Principal.SecurityIdentifier($computersSid)),'ReadAndExecute','Allow')))
Set-Acl -LiteralPath $startup -AclObject $acl
$reader=(New-Object Security.Principal.SecurityIdentifier($computersSid)).Translate([Security.Principal.NTAccount]).Value
$admins=(New-Object Security.Principal.SecurityIdentifier($adminSid)).Translate([Security.Principal.NTAccount]).Value
New-SmbShare -Name $ShareName -Path $target -ReadAccess $reader -FullAccess $admins -FolderEnumerationMode AccessBased -EncryptData $true|Out-Null
Write-Output ('PUBLISHED_WORKSTATIONS='+$plan.Count)
Write-Output ('STARTUP_SCRIPT=\\'+$env:COMPUTERNAME+'.'+$domain.DNSRoot+'\'+$ShareName+'\Start-DomainEndpoint.ps1')
Write-Output 'No GPO was linked. Configure the computer startup policy using DOMAIN-ROLLOUT.md.'
Write-Output 'Only SMB3-capable domain workstations can use this encrypted share.'
