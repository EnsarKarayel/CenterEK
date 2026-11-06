targetScope = 'resourceGroup'

@description('Azure region; select after checking subscription quota and cost.')
param location string = resourceGroup().location
@minLength(3)
@maxLength(12)
param prefix string = 'centerek'
@description('Private VPN/on-premises client IPv4 CIDR. Must not overlap the Azure VNet.')
param clientCidr string
@description('Windows VM administrator; never a GitHub secret.')
param vmAdminUsername string = 'centerekops'
@secure()
@minLength(16)
param vmAdminPassword string
@secure()
@minLength(16)
param initialPanelPassword string
param vmSize string = 'Standard_B2s'
param alertEmail string
@description('Exact GitHub OIDC sub, including immutable owner/repository IDs when enabled. Never use a wildcard.')
param githubSubject string
var suffix = uniqueString(resourceGroup().id)
var vmName = '${prefix}-staging'

resource outboundIp 'Microsoft.Network/publicIPAddresses@2024-05-01' = {
  name: '${prefix}-egress'
  location: location
  sku: { name: 'Standard' }
  properties: { publicIPAllocationMethod: 'Static' }
}
resource nat 'Microsoft.Network/natGateways@2024-05-01' = {
  name: '${prefix}-nat'
  location: location
  sku: { name: 'Standard' }
  properties: { publicIpAddresses: [{ id: outboundIp.id }] }
}
resource nsg 'Microsoft.Network/networkSecurityGroups@2024-05-01' = {
  name: '${prefix}-private-nsg'
  location: location
  properties: {
    securityRules: [
      {
        name: 'AppFromPrivateClients'
        properties: {
          priority: 100
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourceAddressPrefix: clientCidr
          sourcePortRange: '*'
          destinationAddressPrefix: '10.42.1.4'
          destinationPortRange: '8765'
        }
      }
      {
        name: 'DenyOtherInbound'
        properties: {
          priority: 4000
          direction: 'Inbound'
          access: 'Deny'
          protocol: '*'
          sourceAddressPrefix: '*'
          sourcePortRange: '*'
          destinationAddressPrefix: '*'
          destinationPortRange: '*'
        }
      }
    ]
  }
}
resource vnet 'Microsoft.Network/virtualNetworks@2024-05-01' = {
  name: '${prefix}-vnet'
  location: location
  properties: {
    addressSpace: { addressPrefixes: ['10.42.0.0/16'] }
    subnets: [{
      name: 'application'
      properties: {
        addressPrefix: '10.42.1.0/24'
        defaultOutboundAccess: false
        networkSecurityGroup: { id: nsg.id }
        natGateway: { id: nat.id }
      }
    }]
  }
}
resource nic 'Microsoft.Network/networkInterfaces@2024-05-01' = {
  name: '${prefix}-nic'
  location: location
  properties: {
    ipConfigurations: [{
      name: 'private'
      properties: {
        privateIPAllocationMethod: 'Static'
        privateIPAddress: '10.42.1.4'
        subnet: { id: '${vnet.id}/subnets/application' }
      }
    }]
  }
}
resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: 'ce${suffix}'
  location: location
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  properties: {
    supportsHttpsTrafficOnly: true
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
  }
}
resource blobs 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
  properties: {
    isVersioningEnabled: true
    deleteRetentionPolicy: { enabled: true, days: 14 }
  }
}
resource releases 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobs
  name: 'releases'
  properties: { publicAccess: 'None' }
}
resource vm 'Microsoft.Compute/virtualMachines@2024-07-01' = {
  name: vmName
  location: location
  identity: { type: 'SystemAssigned' }
  properties: {
    hardwareProfile: { vmSize: vmSize }
    osProfile: {
      computerName: 'ce-staging'
      adminUsername: vmAdminUsername
      adminPassword: vmAdminPassword
      windowsConfiguration: {
        provisionVMAgent: true
        enableAutomaticUpdates: true
        patchSettings: { patchMode: 'AutomaticByOS' }
      }
    }
    securityProfile: {
      securityType: 'TrustedLaunch'
      uefiSettings: { secureBootEnabled: true, vTpmEnabled: true }
    }
    storageProfile: {
      imageReference: { publisher: 'MicrosoftWindowsServer', offer: 'WindowsServer', sku: '2022-datacenter-g2', version: 'latest' }
      osDisk: {
        createOption: 'FromImage'
        deleteOption: 'Detach'
        managedDisk: { storageAccountType: 'StandardSSD_LRS' }
      }
    }
    networkProfile: { networkInterfaces: [{ id: nic.id }] }
    diagnosticsProfile: { bootDiagnostics: { enabled: true } }
  }
}
resource vault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: 'ce-${suffix}'
  location: location
  properties: {
    tenantId: tenant().tenantId
    sku: { family: 'A', name: 'standard' }
    enableRbacAuthorization: true
    enableSoftDelete: true
    enablePurgeProtection: true
    softDeleteRetentionInDays: 14
  }
}
resource password 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: vault
  name: 'centerek-initial-admin'
  properties: { value: initialPanelPassword }
}
resource vmBlobReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(releases.id, vm.id, 'blob-reader')
  scope: releases
  properties: {
    principalId: vm.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1')
  }
}
resource vmSecretReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(password.id, vm.id, 'secret-reader')
  scope: password
  properties: {
    principalId: vm.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
  }
}
resource pipelineIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${prefix}-github-staging'
  location: location
}
resource federation 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2023-01-31' = {
  parent: pipelineIdentity
  name: 'github-staging'
  properties: {
    issuer: 'https://token.actions.githubusercontent.com'
    subject: githubSubject
    audiences: ['api://AzureADTokenExchange']
  }
}
resource pipelineVmOperator 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(vm.id, pipelineIdentity.id, 'vm-operator')
  scope: vm
  properties: {
    principalId: pipelineIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '9980e02c-c2be-4d73-94e8-173b1dc7cf3c')
  }
}
resource pipelinePublisher 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(releases.id, pipelineIdentity.id, 'publisher')
  scope: releases
  properties: {
    principalId: pipelineIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
  }
}
resource actions 'Microsoft.Insights/actionGroups@2023-01-01' = {
  name: '${prefix}-operations'
  location: 'global'
  properties: {
    groupShortName: 'CenterEK'
    enabled: true
    emailReceivers: [{ name: 'operations', emailAddress: alertEmail, useCommonAlertSchema: true }]
  }
}
resource cpu 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: '${prefix}-cpu-high'
  location: 'global'
  properties: {
    description: 'CenterEK staging CPU > 85% for 15 minutes'
    severity: 2
    enabled: true
    scopes: [vm.id]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT15M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [{ name: 'cpu', metricName: 'Percentage CPU', metricNamespace: 'Microsoft.Compute/virtualMachines', operator: 'GreaterThan', threshold: 85, timeAggregation: 'Average', criterionType: 'StaticThresholdCriterion' }]
    }
    actions: [{ actionGroupId: actions.id }]
  }
}
output vmName string = vm.name
output privatePanelUrl string = 'https://10.42.1.4:8765'
output storageAccount string = storage.name
output keyVaultName string = vault.name
output githubClientId string = pipelineIdentity.properties.clientId
output tenantId string = tenant().tenantId
output subscriptionId string = subscription().subscriptionId
