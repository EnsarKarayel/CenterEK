# Azure browser access

This is a separate access layer for the shared staging installation, not a
customer fork or a public RDP endpoint. The application VM remains private.

## Design

Browser → Azure HTTPS / Microsoft Entra sign-in → explicitly allowed user IDs
→ nginx gateway → verified private HTTPS → CenterEK account and role.

Use the Azure-managed `azurecontainerapps.io` address initially. No purchased
domain is required. Entra access does not grant Azure subscription management.
Additional people need their own approved Entra identity and CenterEK account;
do not share the staging administrator password. Tenant MFA/Conditional Access
must be verified separately; Entra sign-in alone is not proof of enforced MFA.

The Consumption gateway scales from zero to one replica. Requests/compute,
peering and VNet infrastructure can consume trial credit. This is not a promise
of a free production service or DDoS immunity. The existing trial spending limit
must remain enabled. Request limits here cap traffic reaching the application;
they are not an upstream WAF or volumetric DDoS protection plan.

## Release sequence

1. Resolve and review the official nginx image digest; never deploy a moving tag.
2. Read the backend's public CA certificate and DNS SAN, never its private key.
3. Create a single-tenant Entra app with only interactive sign-in scopes. Set
   its exact HTTPS callback and a finite-lived client secret. Store the secret
   in protected local parameters / Container Apps secret, never Git or email.
4. Deploy `infra/azure/browser-access.bicep`. It always starts with **internal**
   ingress and mandatory Entra authentication, an explicit user allowlist, no
   anonymous path exclusions, and no external redirect allowlist.
5. Add the Windows firewall rule for source `10.43.0.0/23` to private port 8765.
   Never widen the office-client rule or expose VM port 8765 / RDP publicly.
6. Verify the live auth configuration and ready revision before enabling public
   HTTPS ingress. Then test TLS, anonymous redirect, anonymous APIs, rejected
   identities, approved Microsoft sign-in and actual CenterEK login. Disable
   public ingress if any of these checks fail; never use `AllowAnonymous` to
   troubleshoot a live gateway.
7. Record the real URL and test results in the local deployment status. Hand off
   the interactive login for user acceptance. Send a link/instructions only
   after validation; passwords and bootstrap files are not email attachments.

Full redeployment of the original private-infrastructure template may remove
the additional NSG child rule. Preserve the gateway rule in that template before
using a full infrastructure redeployment. Application CI deployment does not
redeploy networking. Gateway changes need their own reviewed deployment.

## Product / source control

One maintained product repository and protected main branch; development through
branches and PRs. The Azure staging installation records its deployed commit.
Each customer has its own installation ID, settings, database, secrets, devices,
licensing and update channel. Ship versioned, tested packages instead of making
an independently drifting main branch for every customer. A genuinely separate
customer feature can use a branch/PR; forks only when separate ownership is
intentional. Customer device data and credentials never belong in source control.

## Live staging acceptance · 6 November 2026

Published address:
https://centerek-browser.wonderfulocean-51ea5b45.swedencentral.azurecontainerapps.io

ARM authentication scope validation, normal TLS validation, anonymous requests
to `/`, `/api/status`, `/api/inventory`, `/api/accounts` with spoofed identity
headers, running nginx configuration validation and a real private HTTPS
backend `/healthz` request passed. The owner confirmed Microsoft sign-in reaches
the CenterEK login page. External ingress propagation was observed to lag ARM;
the publication tool now waits and rejects a final 404 or unexpected response.

The enterprise application also requires explicit user assignment. No Graph data
permissions or Azure management roles are granted by this access path.

The 90-day client secret expires on 4 February 2027 and must be rotated before
then. The automatic reminder/rotation feature is not implemented. Second-person
interactive rejection, tenant MFA policy verification, production WAF/rate-limit
acceptance and the owner's actual panel session remain separate acceptance items.
No mail was sent; `ACCESS-EMAIL-TR.md` is a password-free handoff draft.
