#Requires -Version 5.1
<#
.SYNOPSIS
    Deploys or validates DUSK Bedrock Mantle dev-validation infrastructure.
.DESCRIPTION
    Modes:
      (default)        Read-only validation. No AWS or GitHub writes.
      -Deploy -Confirm Creates or updates the CloudFormation stack and sets
                       AWS_ROLE_ARN as a GitHub environment variable.

    This script never dispatches any workflow.
    This script never prints secret values or bearer tokens.
    AWS account ID is printed as deployment context; it is not a secret.

    Unlike the production OIDC script, this targets the dev environment
    (real-agent-dev), validates the deployment branch policy is restricted to
    'dev' only, and confirms the deployed role holds
    bedrock:GetFoundationModelToken (not InvokeModel).

.PARAMETER Deploy
    Enable deployment mode. Requires -Confirm.

.PARAMETER Confirm
    Required when using -Deploy. Acknowledges that AWS IAM resources will be
    created or updated.

.PARAMETER StackName
    CloudFormation stack name. Default: dusk-bedrock-mantle-dev

.PARAMETER GitHubRepo
    GitHub repository in owner/repo format. Default: ShieldTech-Ltd/DUSK

.PARAMETER GitHubEnvironment
    GitHub Actions environment name. Default: real-agent-dev

.PARAMETER TemplatePath
    Path to the CloudFormation template. Default: resolved relative to script.

.PARAMETER ExistingOidcProviderArn
    ARN of an existing GitHub OIDC provider in this account. Leave blank to
    create a new provider. Supply to avoid EntityAlreadyExists errors.

.EXAMPLE
    scripts/setup-bedrock-mantle-dev.ps1
    Validate prerequisites only.

.EXAMPLE
    scripts/setup-bedrock-mantle-dev.ps1 -Deploy -Confirm
    Deploy the CloudFormation stack and configure the GitHub environment var.
#>
[CmdletBinding()]
param(
    [switch]$Deploy,
    [switch]$Confirm,
    [string]$StackName = "dusk-bedrock-mantle-dev",
    [string]$GitHubRepo = "ShieldTech-Ltd/DUSK",
    [string]$GitHubEnvironment = "real-agent-dev",
    [string]$TemplatePath = "",
    [string]$ExistingOidcProviderArn = ""
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $TemplatePath) {
    $TemplatePath = Join-Path $ScriptDir "..\infra\aws\bedrock-mantle-dev\template.yaml"
}
$TemplatePath = Resolve-Path $TemplatePath

$RoleName = "DuskRealAgentDevMantleRole"

function Test-CommandAvailable {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        Write-Error "$Name is not installed or not in PATH. Install it and re-run."
        exit 1
    }
    Write-Host "$Name found: $((Get-Command $Name).Source)"
}

function Get-AwsRegion {
    $region = $env:AWS_DEFAULT_REGION
    if (-not $region) { $region = $env:AWS_REGION }
    if (-not $region) {
        $region = aws configure get region 2>$null
    }
    if (-not $region) {
        Write-Error "AWS region not configured. Set AWS_DEFAULT_REGION or run 'aws configure'."
        exit 1
    }
    return $region
}

# Step 1: Prerequisites
Write-Host "=== Checking prerequisites ==="
Test-CommandAvailable "aws"
Test-CommandAvailable "gh"

# Step 2: AWS authentication
Write-Host ""
Write-Host "=== Verifying AWS authentication ==="
$identityJson = aws sts get-caller-identity --output json 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Error "AWS CLI is not authenticated. Configure credentials and re-run.`n$identityJson"
    exit 1
}
$identity = $identityJson | ConvertFrom-Json
Write-Host "AWS account: $($identity.Account)"
Write-Host "AWS ARN:     $($identity.Arn)"

# Step 3: GitHub CLI authentication
Write-Host ""
Write-Host "=== Verifying GitHub CLI authentication ==="
gh auth status 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Error "GitHub CLI is not authenticated. Run 'gh auth login'."
    exit 1
}
Write-Host "GitHub CLI authenticated."

# Step 4: AWS region
$region = Get-AwsRegion
Write-Host "AWS region: $region"

# Step 5: GitHub environment protection check
Write-Host ""
Write-Host "=== Verifying GitHub environment protection ==="
$envJson = gh api "repos/$GitHubRepo/environments/$GitHubEnvironment" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Error "Could not read environment '$GitHubEnvironment' in $GitHubRepo. Check repo access.`n$envJson"
    exit 1
}
$envInfo = $envJson | ConvertFrom-Json
$reviewerLogins = @()
foreach ($rule in $envInfo.protection_rules) {
    if ($rule.type -eq "required_reviewers") {
        foreach ($reviewer in $rule.reviewers) {
            $reviewerLogins += $reviewer.reviewer.login
        }
    }
}
if ("ritiksah141" -notin $reviewerLogins) {
    Write-Error "SECURITY: Environment '$GitHubEnvironment' does not require ritiksah141 approval. Do not weaken environment protection."
    exit 1
}
Write-Host "Environment protection confirmed: ritiksah141 required as reviewer."

# Step 5b: Validate deployment branch policy restricts to 'dev' only.
# The dev workflow checks github.ref at runtime, but the environment
# deployment_branch_policy is the GitHub-enforced gate that prevents any
# non-dev branch from even entering the environment. Both controls must be in
# place. This dev stack must be restricted to 'dev', never 'main'.
Write-Host ""
Write-Host "=== Verifying environment deployment branch policy (dev only) ==="
$deployPolicy = $envInfo.deployment_branch_policy
if ($null -eq $deployPolicy) {
    Write-Error @"
SECURITY: Environment '$GitHubEnvironment' has no deployment_branch_policy.
Without a branch policy, any branch can deploy to this environment and assume
the Mantle dev OIDC role. Configure the environment to restrict deployments to
the 'dev' branch only.
"@
    exit 1
}

$customBranchPolicy = $deployPolicy.custom_branch_policies

if ($customBranchPolicy -eq $true) {
    $branchPoliciesJson = gh api "repos/$GitHubRepo/environments/$GitHubEnvironment/deployment-branch-policies" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Could not read custom deployment branch policies for '$GitHubEnvironment'.`n$branchPoliciesJson"
        exit 1
    }
    $branchPolicies  = ($branchPoliciesJson | ConvertFrom-Json).branch_policies
    $allowedPatterns = @($branchPolicies | ForEach-Object { $_.name })
    $onlyDevAllowed  = ($allowedPatterns.Count -eq 1) -and ($allowedPatterns[0] -eq "dev")
    if (-not $onlyDevAllowed) {
        Write-Error @"
SECURITY: Environment '$GitHubEnvironment' uses custom_branch_policies but the
allowed patterns are: $($allowedPatterns -join ', ')
Only 'dev' must be allowed. Remove any other patterns (especially 'main') and
re-run.
"@
        exit 1
    }
    Write-Host "Deployment branch policy: custom_branch_policies, pattern=['dev'] only"
} else {
    Write-Error @"
SECURITY: Environment '$GitHubEnvironment' deployment_branch_policy must use
custom_branch_policies restricted to 'dev'. protected_branches is not
acceptable here because it would permit main. Configure a custom branch policy
that allows only 'dev'.
"@
    exit 1
}
Write-Host "Deployment branch restriction confirmed: only 'dev' may deploy to '$GitHubEnvironment'."

# Step 6: Confirm existing variables and secrets are configured
Write-Host ""
Write-Host "=== Checking environment variable and secret presence ==="
$varsJson = gh api "repos/$GitHubRepo/environments/$GitHubEnvironment/variables" 2>&1
$secretsJson = gh api "repos/$GitHubRepo/environments/$GitHubEnvironment/secrets" 2>&1
$configuredVars = @()
$configuredSecrets = @()
if ($LASTEXITCODE -eq 0) {
    $configuredVars = ($varsJson | ConvertFrom-Json).variables.name
    $configuredSecrets = ($secretsJson | ConvertFrom-Json).secrets.name
}

foreach ($varName in @("AWS_REGION", "BEDROCK_PROVIDER", "BEDROCK_MODEL_ID")) {
    if ($varName -in $configuredVars) {
        Write-Host "Variable $varName : configured"
    } else {
        Write-Warning "Variable $varName : NOT configured in '$GitHubEnvironment'"
    }
}

$gateKeyName = "DUSK_GATE_API_KEY"
if ($gateKeyName -in $configuredSecrets) {
    Write-Host "Secret $gateKeyName : present (value not shown)"
} else {
    Write-Warning "Secret $gateKeyName : NOT configured in '$GitHubEnvironment'"
}

if ("AWS_ROLE_ARN" -in $configuredVars) {
    Write-Host "Variable AWS_ROLE_ARN: configured"
} else {
    Write-Warning "Variable AWS_ROLE_ARN: NOT configured (will be set after deployment)"
}

# Validate OIDC subject in the template restricts to real-agent-dev exactly.
Write-Host ""
Write-Host "=== Verifying template OIDC subject (real-agent-dev only) ==="
$templateText = Get-Content -Raw -Path $TemplatePath
if ($templateText -notmatch "environment:\$\{GitHubEnvironment\}" -and $templateText -notmatch "environment:real-agent-dev") {
    Write-Error "Template OIDC subject does not restrict to the real-agent-dev environment."
    exit 1
}
if ($GitHubEnvironment -ne "real-agent-dev") {
    Write-Error "GitHubEnvironment must be 'real-agent-dev' for the dev Mantle stack; got '$GitHubEnvironment'."
    exit 1
}
Write-Host "Template OIDC subject restricts to environment:real-agent-dev."

# Validate-only path
if (-not $Deploy) {
    Write-Host ""
    Write-Host "Validation complete. No AWS or GitHub changes were made."
    Write-Host "Run with -Deploy -Confirm to create the CloudFormation stack."
    exit 0
}

# Step 7: Require explicit confirmation
if (-not $Confirm) {
    Write-Error "Add -Confirm to acknowledge that AWS IAM resources will be created or updated."
    exit 1
}

# Step 8: Deploy CloudFormation stack
Write-Host ""
Write-Host "=== Deploying CloudFormation stack: $StackName ==="

$overrides = @(
    "GitHubOrg=ShieldTech-Ltd"
    "GitHubRepo=DUSK"
    "GitHubEnvironment=$GitHubEnvironment"
    "RoleName=$RoleName"
)
if ($ExistingOidcProviderArn) {
    $overrides += "ExistingOidcProviderArn=$ExistingOidcProviderArn"
}

aws cloudformation deploy `
    --stack-name $StackName `
    --template-file $TemplatePath `
    --parameter-overrides @overrides `
    --capabilities CAPABILITY_NAMED_IAM `
    --region $region `
    --no-fail-on-empty-changeset

if ($LASTEXITCODE -ne 0) {
    Write-Error "CloudFormation deployment failed. Check the AWS console for stack events."
    exit 1
}
Write-Host "Stack deployed successfully."

# Step 9: Capture RoleArn output
$outputsJson = aws cloudformation describe-stacks `
    --stack-name $StackName `
    --region $region `
    --query "Stacks[0].Outputs" `
    --output json
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to read stack outputs."
    exit 1
}
$outputs = $outputsJson | ConvertFrom-Json
$roleArn = ($outputs | Where-Object { $_.OutputKey -eq "RoleArn" }).OutputValue

if (-not $roleArn) {
    Write-Error "RoleArn not found in stack outputs."
    exit 1
}
Write-Host "RoleArn: $roleArn"

# Step 10: Validate the deployed role holds GetFoundationModelToken.
Write-Host ""
Write-Host "=== Validating GetFoundationModelToken permission on deployed role ==="
$policyNamesJson = aws iam list-role-policies --role-name $RoleName --output json 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Error "Could not list inline policies for role '$RoleName'.`n$policyNamesJson"
    exit 1
}
$policyNames = ($policyNamesJson | ConvertFrom-Json).PolicyNames
$foundToken = $false
foreach ($policyName in $policyNames) {
    $policyJson = aws iam get-role-policy --role-name $RoleName --policy-name $policyName --output json 2>&1
    if ($LASTEXITCODE -ne 0) { continue }
    if ($policyJson -match "GetFoundationModelToken") {
        $foundToken = $true
    }
    if ($policyJson -match "bedrock:InvokeModel") {
        Write-Error "SECURITY: Role '$RoleName' unexpectedly grants bedrock:InvokeModel. The Mantle dev role must only grant GetFoundationModelToken."
        exit 1
    }
}
if (-not $foundToken) {
    Write-Error "Role '$RoleName' does not grant bedrock:GetFoundationModelToken. The Mantle client cannot mint a bearer token."
    exit 1
}
Write-Host "Confirmed: role grants bedrock:GetFoundationModelToken and not InvokeModel."

# Step 11: Set AWS_ROLE_ARN as GitHub environment variable (not a secret)
Write-Host ""
Write-Host "=== Setting AWS_ROLE_ARN GitHub environment variable ==="
gh variable set AWS_ROLE_ARN `
    --body $roleArn `
    --env $GitHubEnvironment `
    --repo $GitHubRepo

if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to set AWS_ROLE_ARN. Check gh auth permissions."
    exit 1
}
Write-Host "AWS_ROLE_ARN configured in environment '$GitHubEnvironment'."

Write-Host ""
Write-Host "=== Setup complete ==="
Write-Host "This script does not dispatch the validation workflow."
Write-Host ""
Write-Host "Next steps (manual, after PR is merged to dev):"
Write-Host "  1. Ensure BEDROCK_PROVIDER=mantle and BEDROCK_MODEL_ID are set in the environment."
Write-Host "  2. Trigger the workflow via GitHub Actions UI (requires ritiksah141 approval)."
Write-Host "  3. Do not dispatch automatically from this script."
