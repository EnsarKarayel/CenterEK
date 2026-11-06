param([Parameter(Mandatory=$true)][string]$ArtifactFolder,
      [Parameter(Mandatory=$true)][ValidatePattern('^[a-f0-9]{40}$')][string]$Commit)
$ErrorActionPreference='Stop'
foreach($name in @('AZURE_RESOURCE_GROUP','AZURE_VM_NAME','AZURE_STORAGE_ACCOUNT','AZURE_KEY_VAULT','AZURE_CLIENT_CIDR')){
    if(-not [Environment]::GetEnvironmentVariable($name)){throw ('Missing deployment setting: '+$name)}
}
if($env:AZURE_STORAGE_ACCOUNT -notmatch '^[a-z0-9]{3,24}$'){throw 'Invalid storage account'}
$manifest=Get-Content -LiteralPath (Join-Path $ArtifactFolder 'release-manifest.json') -Raw|ConvertFrom-Json
if($manifest.commit -cne $Commit){throw 'Artifact commit does not match the tested commit'}
if($manifest.archive -ne [IO.Path]::GetFileName($manifest.archive)){throw 'Invalid artifact path'}
$archive=Join-Path $ArtifactFolder $manifest.archive
if((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant() -cne $manifest.sha256){throw 'Artifact digest mismatch'}
$blob=$Commit+'/'+$manifest.sha256+'.zip'
$exists=& az storage blob exists --auth-mode login --account-name $env:AZURE_STORAGE_ACCOUNT --container-name releases --name $blob --query exists --output tsv --only-show-errors
if($LASTEXITCODE){throw 'Artifact storage check failed; refusing deployment'}
if($exists -eq 'true'){
    $metadata=& az storage blob show --auth-mode login --account-name $env:AZURE_STORAGE_ACCOUNT --container-name releases --name $blob --query metadata --output json --only-show-errors
    if($LASTEXITCODE){throw 'Existing artifact verification failed'}
    $metadata=$metadata|ConvertFrom-Json
    if($metadata.sha256 -cne $manifest.sha256 -or $metadata.commit -cne $Commit){throw 'Existing immutable artifact metadata mismatch'}
}else{
    & az storage blob upload --auth-mode login --account-name $env:AZURE_STORAGE_ACCOUNT --container-name releases --name $blob --file $archive --metadata ('sha256='+$manifest.sha256) ('commit='+$Commit) --overwrite false --only-show-errors --output none
    if($LASTEXITCODE){throw 'Artifact upload failed; refusing deployment'}
}
$script=Join-Path $PSScriptRoot 'Deploy-Guest.ps1'
$resultFile=Join-Path $ArtifactFolder 'azure-run-command.json'
& az vm run-command invoke --resource-group $env:AZURE_RESOURCE_GROUP --name $env:AZURE_VM_NAME --command-id RunPowerShellScript --scripts ('@'+$script) --parameters ('StorageAccount='+$env:AZURE_STORAGE_ACCOUNT) ('BlobName='+$blob) ('ArchiveSHA256='+$manifest.sha256) ('Commit='+$Commit) ('VaultName='+$env:AZURE_KEY_VAULT) ('ClientCIDR='+$env:AZURE_CLIENT_CIDR) --output json | Set-Content -LiteralPath $resultFile -Encoding utf8
if($LASTEXITCODE){throw 'Azure VM Run Command request failed'}
$result=Get-Content -LiteralPath $resultFile -Raw|ConvertFrom-Json
$messages=($result.value|ForEach-Object {$_.message}) -join "`n"
if($messages -notmatch ('CENTEREK_DEPLOY_OK '+$Commit)){
    Write-Output $messages
    throw 'Guest deployment failed or rolled back; inspect Azure Run Command and the private guest deployment log'
}
Write-Output ('Verified Azure staging deployment: '+$Commit)
