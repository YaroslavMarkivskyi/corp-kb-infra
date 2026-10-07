targetScope = 'resourceGroup'

@description('Azure region for the infrastructure resources.')
param location string = 'westeurope'

@description('Cost allocation identifier applied to every resource.')
param costCenter string = 'CC-1000'

@description('Email address for the project manager receiving budget alerts.')
param pmEmail string

@description('First day of the next month, when the monthly budget begins.')
param budgetStartDate string = dateTimeAdd(utcNow('yyyy-MM-01T00:00:00Z'), 'P1M')

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

resource monthlyBudget 'Microsoft.Consumption/budgets@2021-10-01' = {
  name: 'monthly-budget'
  properties: {
    amount: 200
    category: 'Cost'
    timeGrain: 'Monthly'
    timePeriod: {
      startDate: budgetStartDate
    }
    notifications: {
      alertAt80Percent: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 80
        contactEmails: [
          'it-ops@company.com'
          pmEmail
        ]
      }
      alertAt100Percent: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 100
        contactEmails: [
          'it-ops@company.com'
          pmEmail
        ]
      }
    }
  }
}
