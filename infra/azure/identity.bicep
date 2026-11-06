targetScope = 'resourceGroup'
param location string = resourceGroup().location
param prefix string = 'centerek'
param githubRepository string = 'EnsarKarayel/CenterEK'
param githubEnvironment string = 'azure-staging'

// Identity-only bootstrap: no VM, disk, NAT, public endpoint or client secret.
resource pipeline 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${prefix}-github-staging'
  location: location
}
resource federation 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2023-01-31' = {
  parent: pipeline
  name: 'github-staging'
  properties: {
    issuer: 'https://token.actions.githubusercontent.com'
    subject: 'repo:${githubRepository}:environment:${githubEnvironment}'
    audiences: ['api://AzureADTokenExchange']
  }
}
resource readGroup 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, pipeline.id, 'connection-readonly')
  properties: {
    principalId: pipeline.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'acdd72a7-3385-48ef-bd42-f606fba81ae7')
  }
}
output clientId string = pipeline.properties.clientId
output tenantId string = tenant().tenantId
output subscriptionId string = subscription().subscriptionId
