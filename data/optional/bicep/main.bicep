// Provisions the Azure resources this project needs.
//
// Deploy:
//   az deployment group create \
//     --resource-group <your-rg> \
//     --template-file main.bicep \
//     --parameters projectName=<yourteam>
//
// param = an input you pass at deploy time.
param location string = resourceGroup().location
param projectName string

module storage 'modules/storage.bicep' = {
  name: 'storageDeploy'
  params: {
    location: location
    storageName: 'st${toLower(projectName)}'
  }
}

output storageId string = storage.outputs.storageId
