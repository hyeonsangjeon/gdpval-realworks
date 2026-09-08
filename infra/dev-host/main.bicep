// The development host the Xenology card gates on, as a definition rather than
// as a sequence of portal clicks.
//
// Conditions 1 and 5 of that card fired on 2026-09-08 and have been firing
// since at least 2026-09-03: the development box runs a 3.10 kernel, so this
// repository's seccomp and user-namespace verifications do not run there — they
// skip, which is worse than failing, because a regression in the agentic
// launcher's deny-exec and deny-socket behaviour would pass unnoticed. The card
// says build the VM when one of the five reproduces. Two have.
//
// Everything the card fixes is a parameter with the card's value as its
// default, so a deviation has to be typed rather than drifted into, and
// scripts/check_dev_host_definition.py reads this file and holds each one.
//
// Scope: a resource group in the *external* subscription
// ME-MngEnvMCAP756842-hjeon-1. This definition is never deployed into the
// internal subscription that carries the Foundry permissions — see the
// subscription guard in deploy.sh, which refuses rather than warns.
//
// What this deliberately does not contain:
//
//   * No inbound SSH rule unless a source prefix is named. The default is a
//     network security group whose only inbound rule is a deny, and a network
//     interface with no public address at all. `az vm run-command` reaches the
//     machine through the Azure agent with no listening port, which is enough
//     to bootstrap it and to run the diagnostic. A person who wants an
//     interactive session names their own address; nobody gets 0.0.0.0/0 by
//     forgetting a parameter.
//   * No role assignment. The virtual machine gets a system-assigned identity,
//     because the card forbids storing long-lived Azure keys on it and an
//     identity is the alternative — but an identity with no role can do
//     nothing, and granting it one is a permission change that belongs in a
//     request, not in a default.
//   * No password authentication. Not "a strong password": the property is off,
//     and the definition will not deploy without a public key.
//   * No benchmark role. This is a development and test host. The pre-registered
//     GDPVal execution environments are not silently re-pointed at it; that
//     contract is enforced in code by batch-runner/dev_host_boundary.py, not
//     promised here.

targetScope = 'resourceGroup'

@description('Where the machine lives. The card fixes koreacentral and says another region may be chosen only for SKU availability or quota, and only if the reason is written down.')
param location string = 'koreacentral'

@description('Name stem for every resource, so one deployment is one recognisable set and `az group delete` is a complete teardown.')
@minLength(3)
@maxLength(24)
param namePrefix string = 'gdpval-devhost'

@description('8 vCPU / 32 GiB, which is the card\'s starting size. It says to grow only after measuring, so growing this without a measurement is a deviation the checker reports.')
param vmSize string = 'Standard_D8as_v5'

@description('The administrative account name. Not root, and not a name that a scanner tries first.')
param adminUsername string = 'gdpval'

@description('OpenSSH public key. There is no password path: disablePasswordAuthentication is true below and this parameter has no default, so a deployment without a key fails rather than falling back to one.')
@secure()
param adminPublicKey string

@description('Source addresses allowed to reach port 22, as CIDR. Empty — the default — means no inbound rule is created at all and the machine is reachable only through the Azure agent. `["*"]` and `["Internet"]` are refused by scripts/check_dev_host_definition.py, and by the assertion below.')
param sshAllowedSourcePrefixes array = []

@description('Give the machine a public address. Off by default. With no public address and no inbound rule, `az vm run-command` is the only way in, which is the card\'s "가능하면 사설 연결을 사용한다" taken literally.')
param attachPublicIp bool = false

@description('Ubuntu 24.04 LTS, the card\'s operating system. Held by the checker: this is not a place to quietly substitute a different image because it happens to sandbox more easily.')
param imagePublisher string = 'Canonical'
param imageOffer string = 'ubuntu-24_04-lts'
param imageSku string = 'server'

@description('`latest` is what the card asks for. The exact version that was resolved is recorded by deploy.sh into the provenance file, because "latest" is not a thing a later reader can reproduce from.')
param imageVersion string = 'latest'

@description('Operating system disk, GiB. Docker layers and test artifacts go on the data disk below, not here.')
@minValue(64)
param osDiskSizeGb int = 128

@description('Data disk for container layers, checkouts and test output. The card asks for enough managed disk to hold them and for artifacts to be recovered to the repository or a separate store rather than left here.')
@minValue(128)
param dataDiskSizeGb int = 512

@description('Local time the machine shuts down every day, HHmm. This is a deallocating stop — the billing kind — not a guest shutdown, which would leave the machine stopped and still charged.')
param autoShutdownTime string = '2100'

@description('Time zone the shutdown time is read in.')
param autoShutdownTimeZone string = 'Korea Standard Time'

@description('Address to notify before the automatic shutdown. Empty disables the notification; the shutdown still happens.')
param autoShutdownNotificationEmail string = ''

@description('Tags applied to everything, so cost can be attributed and so a sweep can find every resource this definition made.')
param tags object = {
  purpose: 'gdpval-realworks development and test host'
  card: 'Xenology 개발 작업을 Azure VM으로 이전하는 기준과 실행 호스트 마련'
  benchmark_execution_environment: 'no'
  managed_by: 'infra/dev-host/main.bicep'
}

// A wildcard here would be the one mistake that matters, so it is refused at
// deployment time as well as by the offline checker. Both, because the checker
// reads the file and this reads the arguments, and they fail at different
// moments for different reasons.
var wildcardSources = filter(sshAllowedSourcePrefixes, prefix => prefix == '*' || prefix == '0.0.0.0/0' || toLower(string(prefix)) == 'internet' || toLower(string(prefix)) == 'any')

@description('Refuses a wildcard SSH source. The card allows port 22 from approved origins only.')
var _sshSourceGuard = length(wildcardSources) == 0 ? true : fail('sshAllowedSourcePrefixes may not contain a wildcard: ${wildcardSources}. Name the addresses that are allowed, or leave it empty and reach the machine with `az vm run-command`.')

var vnetName = '${namePrefix}-vnet'
var subnetName = '${namePrefix}-subnet'
var nsgName = '${namePrefix}-nsg'
var nicName = '${namePrefix}-nic'
var publicIpName = '${namePrefix}-pip'
var vmName = '${namePrefix}-vm'
var dataDiskName = '${namePrefix}-data'

resource nsg 'Microsoft.Network/networkSecurityGroups@2023-11-01' = {
  name: nsgName
  location: location
  tags: tags
  properties: {
    securityRules: concat(
      // Only exists when somebody named an address. There is no branch of this
      // template that produces an allow rule with a wildcard source.
      empty(sshAllowedSourcePrefixes) ? [] : [
        {
          name: 'allow-ssh-from-named-sources'
          properties: {
            description: 'Port 22 from the addresses the operator named. Never from the internet at large.'
            protocol: 'Tcp'
            sourcePortRange: '*'
            destinationPortRange: '22'
            sourceAddressPrefixes: sshAllowedSourcePrefixes
            destinationAddressPrefix: '*'
            access: 'Allow'
            direction: 'Inbound'
            priority: 300
          }
        }
      ],
      // Azure denies unmatched inbound traffic anyway. This rule is written out
      // so that the intent is visible in `az network nsg rule list` rather than
      // being an absence somebody has to notice, and so that a later rule added
      // by hand above priority 4000 is a deliberate act.
      [
        {
          name: 'deny-all-other-inbound'
          properties: {
            description: 'Everything not named above. Written down rather than left implicit.'
            protocol: '*'
            sourcePortRange: '*'
            destinationPortRange: '*'
            sourceAddressPrefix: '*'
            destinationAddressPrefix: '*'
            access: 'Deny'
            direction: 'Inbound'
            priority: 4000
          }
        }
      ]
    )
  }
}

resource vnet 'Microsoft.Network/virtualNetworks@2023-11-01' = {
  name: vnetName
  location: location
  tags: tags
  properties: {
    addressSpace: {
      addressPrefixes: ['10.42.0.0/16']
    }
    subnets: [
      {
        name: subnetName
        properties: {
          addressPrefix: '10.42.1.0/24'
          networkSecurityGroup: {
            id: nsg.id
          }
        }
      }
    ]
  }
}

resource publicIp 'Microsoft.Network/publicIPAddresses@2023-11-01' = if (attachPublicIp) {
  name: publicIpName
  location: location
  tags: tags
  sku: {
    name: 'Standard'
  }
  properties: {
    publicIPAllocationMethod: 'Static'
  }
}

resource nic 'Microsoft.Network/networkInterfaces@2023-11-01' = {
  name: nicName
  location: location
  tags: tags
  properties: {
    ipConfigurations: [
      {
        name: 'ipconfig1'
        properties: {
          subnet: {
            id: '${vnet.id}/subnets/${subnetName}'
          }
          privateIPAllocationMethod: 'Dynamic'
          publicIPAddress: attachPublicIp ? { id: publicIp.id } : null
        }
      }
    ]
  }
}

resource dataDisk 'Microsoft.Compute/disks@2023-10-02' = {
  name: dataDiskName
  location: location
  tags: tags
  sku: {
    name: 'Premium_LRS'
  }
  properties: {
    creationData: {
      createOption: 'Empty'
    }
    diskSizeGB: dataDiskSizeGb
  }
}

resource vm 'Microsoft.Compute/virtualMachines@2024-07-01' = {
  name: vmName
  location: location
  tags: tags
  // System-assigned only, and with no role assignment anywhere in this file.
  // The card forbids long-lived Azure keys on the machine; an identity is how
  // that is satisfied without them. What the identity may *do* is a separate
  // decision that has to be asked for.
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    hardwareProfile: {
      vmSize: vmSize
    }
    storageProfile: {
      imageReference: {
        publisher: imagePublisher
        offer: imageOffer
        sku: imageSku
        version: imageVersion
      }
      osDisk: {
        createOption: 'FromImage'
        diskSizeGB: osDiskSizeGb
        managedDisk: {
          storageAccountType: 'Premium_LRS'
        }
        deleteOption: 'Delete'
      }
      dataDisks: [
        {
          lun: 0
          createOption: 'Attach'
          managedDisk: {
            id: dataDisk.id
          }
          deleteOption: 'Detach'
        }
      ]
    }
    osProfile: {
      computerName: vmName
      adminUsername: adminUsername
      linuxConfiguration: {
        // The whole password path, off. Not a policy, a property.
        disablePasswordAuthentication: true
        ssh: {
          publicKeys: [
            {
              path: '/home/${adminUsername}/.ssh/authorized_keys'
              keyData: adminPublicKey
            }
          ]
        }
        patchSettings: {
          patchMode: 'ImageDefault'
        }
      }
    }
    networkProfile: {
      networkInterfaces: [
        {
          id: nic.id
        }
      ]
    }
    securityProfile: {
      securityType: 'TrustedLaunch'
      uefiSettings: {
        secureBootEnabled: true
        vTpmEnabled: true
      }
    }
    diagnosticsProfile: {
      bootDiagnostics: {
        enabled: true
      }
    }
  }
}

// A deallocating stop, every day, whether or not anybody remembered. The
// distinction matters for the bill: a `shutdown -h` issued inside the guest
// leaves the machine Stopped and still charged for its compute reservation,
// whereas this task deallocates.
//
// It is a ceiling, not an idle policy. Deallocating the moment work stops would
// need the machine to call Azure about itself, which needs a role assignment on
// its identity — a permission change, so it is asked for rather than assumed.
// Until then the idle case is a person running `deploy.sh deallocate`, and
// this schedule is what catches the day they forget.
resource autoShutdown 'Microsoft.DevTestLab/schedules@2018-09-15' = {
  name: 'shutdown-computevm-${vmName}'
  location: location
  tags: tags
  properties: {
    status: 'Enabled'
    taskType: 'ComputeVmShutdownTask'
    dailyRecurrence: {
      time: autoShutdownTime
    }
    timeZoneId: autoShutdownTimeZone
    notificationSettings: {
      status: empty(autoShutdownNotificationEmail) ? 'Disabled' : 'Enabled'
      timeInMinutes: 30
      emailRecipient: autoShutdownNotificationEmail
    }
    targetResourceId: vm.id
  }
}

output vmName string = vm.name
output vmId string = vm.id
output principalId string = vm.identity.principalId
output privateIpAddress string = nic.properties.ipConfigurations[0].properties.privateIPAddress
output publicIpAddress string = attachPublicIp ? publicIp!.properties.ipAddress : ''
output inboundSshRuleExists bool = !empty(sshAllowedSourcePrefixes)
output autoShutdownSchedule string = '${autoShutdownTime} ${autoShutdownTimeZone}'
output sshSourceGuardPassed bool = _sshSourceGuard
