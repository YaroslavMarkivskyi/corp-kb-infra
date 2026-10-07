targetScope = 'subscription'

resource approvedRegionsPolicy 'Microsoft.Authorization/policyDefinitions@2021-06-01' = {
  name: 'approved-regions'
  properties: {
    displayName: 'Allow resources only in approved regions'
    policyType: 'Custom'
    mode: 'Indexed'
    policyRule: {
      if: {
        field: 'location'
        notIn: [
          'germanywestcentral'
          'westeurope'
        ]
      }
      then: {
        effect: 'deny'
      }
    }
  }
}

resource costCenterPolicy 'Microsoft.Authorization/policyDefinitions@2021-06-01' = {
  name: 'require-cost-center'
  properties: {
    displayName: 'Require a CostCenter tag'
    policyType: 'Custom'
    mode: 'Indexed'
    policyRule: {
      if: {
        field: 'tags[\'CostCenter\']'
        exists: false
      }
      then: {
        effect: 'deny'
      }
    }
  }
}

resource approvedRegionsAssignment 'Microsoft.Authorization/policyAssignments@2022-06-01' = {
  name: 'enforce-approved-regions'
  properties: {
    displayName: 'Enforce approved regions'
    policyDefinitionId: approvedRegionsPolicy.id
  }
}

resource costCenterAssignment 'Microsoft.Authorization/policyAssignments@2022-06-01' = {
  name: 'enforce-cost-center'
  properties: {
    displayName: 'Enforce CostCenter tag'
    policyDefinitionId: costCenterPolicy.id
  }
}
