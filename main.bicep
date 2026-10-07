targetScope = 'resourceGroup'

@description('Azure region for the infrastructure resources.')
#disable-next-line no-unused-params
param location string = 'westeurope'

@description('Cost allocation identifier applied to every resource.')
#disable-next-line no-unused-params
param costCenter string = 'CC-1000'

@description('Monthly Cost Management budget amount.')
param budgetAmount int = 200

@description('Email address for IT Operations receiving budget alerts.')
param itOpsEmail string = 'it-ops@company.com'

@description('Email address for the project manager receiving budget alerts.')
param pmEmail string

@description('First day of the next month, when the monthly budget begins.')
param budgetStartDate string = dateTimeAdd(utcNow('yyyy-MM-01T00:00:00Z'), 'P1M')

module budget './modules/budget.bicep' = {
  name: 'monthly-budget'
  params: {
    budgetAmount: budgetAmount
    itOpsEmail: itOpsEmail
    pmEmail: pmEmail
    budgetStartDate: budgetStartDate
  }
}
