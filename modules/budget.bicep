@description('Monthly Cost Management budget amount.')
param budgetAmount int

@description('Email address for IT Operations receiving budget alerts.')
param itOpsEmail string

@description('Email address for the project manager receiving budget alerts.')
param pmEmail string

@description('First day of the next month, when the monthly budget begins.')
param budgetStartDate string

resource monthlyBudget 'Microsoft.Consumption/budgets@2021-10-01' = {
  name: 'monthly-budget'
  properties: {
    amount: budgetAmount
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
          itOpsEmail
          pmEmail
        ]
      }
      alertAt100Percent: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 100
        contactEmails: [
          itOpsEmail
          pmEmail
        ]
      }
    }
  }
}
