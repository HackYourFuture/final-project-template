// ADLS Gen2 storage account for the raw files your pipeline lands.
//
// "ADLS Gen2" is a normal storage account with one setting flipped:
// isHnsEnabled. That turns flat blob names into real folders, which is what
// lets Databricks read `.../raw/postings/2026-08-10.json` as a path rather
// than as a blob whose name happens to contain slashes.

@description('Azure region. Keep it the same as your other resources: cross-region reads cost money and add latency.')
param location string

@description('Storage account name. Globally unique, 3 to 24 characters, lowercase letters and digits only. No dashes.')
@minLength(3)
@maxLength(24)
param storageName string

@description('Name of the container raw files land in.')
param containerName string = 'raw'

@description('Delete raw files older than this many days. 0 keeps everything forever. Decide this with your team: raw files are cheap, but not free.')
param retentionDays int = 90

resource storage 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageName
  location: location
  sku: {
    // Standard_LRS keeps three copies in one datacentre. Enough for a project.
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    // The one setting that makes this ADLS Gen2 rather than plain blob storage.
    isHnsEnabled: true
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    // No account keys. Every reader and writer authenticates as itself, with a
    // managed identity or your own Azure login, so there is no key to leak in
    // a .env file or a chat message.
    allowSharedKeyAccess: false
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-01-01' = {
  parent: storage
  name: 'default'
}

resource rawContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  parent: blobService
  name: containerName
  properties: {
    publicAccess: 'None'
  }
}

// Deleting old raw files is a policy, not a script you have to remember to run.
resource lifecycle 'Microsoft.Storage/storageAccounts/managementPolicies@2023-01-01' = if (retentionDays > 0) {
  parent: storage
  name: 'default'
  properties: {
    policy: {
      rules: [
        {
          name: 'expire-raw'
          enabled: true
          type: 'Lifecycle'
          definition: {
            filters: {
              blobTypes: ['blockBlob']
              prefixMatch: ['${containerName}/']
            }
            actions: {
              baseBlob: {
                delete: {
                  daysAfterModificationGreaterThan: retentionDays
                }
              }
            }
          }
        }
      ]
    }
  }
}

output storageName string = storage.name
output storageId string = storage.id
output containerName string = rawContainer.name

@description('The abfss path your pipeline writes to and Databricks reads from.')
output abfssPath string = 'abfss://${containerName}@${storage.name}.dfs.${environment().suffixes.storage}'
