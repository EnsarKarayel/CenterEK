// Machine-only telemetry. Browser access remains behind the separate Entra app.
targetScope = 'resourceGroup'
param location string
param environmentName string = 'centerek-browser-env'
param appName string = 'centerek-telemetry'
param gatewayImage string
@secure()
param backendCaPem string
@secure()
param nginxConfig string
resource managedEnvironment 'Microsoft.App/managedEnvironments@2025-07-01' existing = {
  name: environmentName
}
resource ingress 'Microsoft.App/containerApps@2025-07-01' = {
  name: appName
  location: location
  properties: {
    environmentId: managedEnvironment.id
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: { external: false, allowInsecure: false, targetPort: 8080, transport: 'http' }
      secrets: [{ name: 'backend-ca', value: backendCaPem }, { name: 'nginx-config', value: nginxConfig }]
    }
    template: {
      containers: [{
        name: 'telemetry-ingress'
        image: gatewayImage
        command: ['nginx']
        args: ['-c', '/etc/centerek/nginx.conf', '-g', 'daemon off;']
        resources: { cpu: json('0.25'), memory: '0.5Gi' }
        volumeMounts: [{ volumeName: 'configuration', mountPath: '/etc/centerek' }]
        probes: [{ type: 'Readiness', tcpSocket: { port: 8080 }, initialDelaySeconds: 2, periodSeconds: 5 }]
      }]
      volumes: [{
        name: 'configuration'
        storageType: 'Secret'
        secrets: [{ secretRef: 'backend-ca', path: 'backend-ca.pem' }, { secretRef: 'nginx-config', path: 'nginx.conf' }]
      }]
      scale: {
        minReplicas: 0
        maxReplicas: 1
        rules: [{ name: 'http', http: { metadata: { concurrentRequests: '10' } } }]
      }
    }
  }
}
output origin string = 'https://${replace(ingress.properties.configuration.ingress.fqdn, '.internal.', '.')}'
output externalIngressEnabled bool = false
