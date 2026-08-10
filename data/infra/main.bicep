// Provisions the storage your pipeline lands raw files in.
//
// Deploy:
//   az deployment group create \
//     --resource-group <your-rg> \
//     --template-file main.bicep \
//     --parameters teamName=<yourteam>
//
// Run it again whenever you change something. Bicep is declarative: it makes
// Azure match this file, so a second deploy with no changes does nothing.

targetScope = 'resourceGroup'

@description('Your team, lowercase, no dashes: teama, teamb or teamc. Used to build resource names.')
@minLength(3)
@maxLength(10)
param teamName string

param location string = resourceGroup().location

@description('Delete raw files older than this many days. 0 keeps everything.')
param retentionDays int = 90

@description('Principal id of the identity that writes raw files: your Container Apps job. Leave empty on the first deploy, then fill it in once the job exists and deploy again.')
param ingestPrincipalId string = ''

// uniqueString keeps the name globally unique without you inventing one. It is
// deterministic, so the same resource group always produces the same name.
// take() trims the hash so the name stays inside the 24 character limit.
var storageName = 'st${teamName}${take(uniqueString(resourceGroup().id), 8)}'

module storage 'modules/storage.bicep' = {
  name: 'storage'
  params: {
    location: location
    storageName: storageName
    retentionDays: retentionDays
  }
}

// Storage Blob Data Contributor. The role your ingestion job needs to write
// files, and nothing more: it cannot delete the container or change access.
var blobContributor = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
)

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' existing = {
  name: storageName
  dependsOn: [storage]
}

resource ingestRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(ingestPrincipalId)) {
  scope: storageAccount
  // The name must be a GUID, and the same inputs must always produce the same
  // one, or every deploy tries to create a duplicate assignment and fails.
  name: guid(storageAccount.id, ingestPrincipalId, blobContributor)
  properties: {
    roleDefinitionId: blobContributor
    principalId: ingestPrincipalId
    principalType: 'ServicePrincipal'
  }
}

output storageName string = storage.outputs.storageName
output abfssPath string = storage.outputs.abfssPath

@description('Give this to your teacher: Databricks needs it to point your landing volume at this container.')
output storageId string = storage.outputs.storageId
