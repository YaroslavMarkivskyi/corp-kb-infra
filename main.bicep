targetScope = 'resourceGroup'

@description('Azure region for the infrastructure resources.')
param location string = 'westeurope'

@description('Cost allocation identifier applied to every resource.')
param costCenter string = 'CC-1000'

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: 'st${uniqueString(resourceGroup().id)}'
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  tags: {
    CostCenter: costCenter
  }
  properties: {
    accessTier: 'Hot'
  }
}
