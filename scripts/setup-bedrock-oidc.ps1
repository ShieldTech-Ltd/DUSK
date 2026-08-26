#Requires -Version 5.1
<#
.SYNOPSIS
    Deploys or validates DUSK Bedrock OIDC infrastructure.
.DESCRIPTION
    Modes:
      (default)        Read-only validation. No AWS or GitHub writes.
      -Deploy -Confirm Creates or updates the CloudFormation stack and sets
                       AWS_ROLE_ARN as a GitHub environment variable.

    This script never dispatches the real-agent workflow.
    This script never prints secret values.
    AWS account ID is printed as deployment context; it is not a secret.

.PARAMETER Deploy
    Enable deployment mode. Requires -Confirm.

.PARAMETER Confirm
    Required when using -Deploy. Acknowledges that AWS IAM resources will be
    created or updated.

.PARAMETER StackName
    CloudFormation stack name. Default: dusk-bedrock-real-agent

.PARAMETER GitHubRepo
    GitHub repository in owner/repo format. Default: ShieldTech-Ltd/DUSK

.PARAMETER GitHubEnvironment
    GitHub Actions environment name. Default: real-agent

.PARAMETER TemplatePath
    Path to the CloudFormation template. Default: resolved relative to script.

.PARAMETER ExistingOidcProviderArn
    ARN of an existing GitHub OIDC provider in this account. Leave blank to
    create a new provider. Supply to avoid EntityAlreadyExists errors.

.EXAMPLE
    scripts/setup-bedrock-oidc.ps1
    Validate prerequisites only.

.EXAMPLE
    scripts/setup-bedrock-oidc.ps1 -Deploy -Confirm
    Deploy the CloudFormation stack and configure GitHub environment variable.
#>
[CmdletBinding()]
param(
    [switch]$Deploy,
    [switch]$Confirm,
    [string]$StackName = "dusk-bedrock-real-agent",
    [string]$GitHubRepo = "ShieldTech-Ltd/DUSK",
    [string]$GitHubEnvironment = "real-agent",
    [string]$TemplatePath = "",
    [string]$ExistingOidcProviderArn = ""
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $TemplatePath) {
    $TemplatePath = Join-Path $ScriptDir "..\infra\aws\bedrock-real-agent\template.yaml"
}
$TemplatePath = Resolve-Path $TemplatePath

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

# Step 5: Bedrock model availability
Write-Host ""
Write-Host "=== Validating Bedrock model availability ==="
$modelId = "anthropic.claude-3-5-sonnet-20241022-v2:0"
$modelJson = aws bedrock get-foundation-model `
    --model-identifier $modelId `
    --region $region `
    --output json 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Error @"
Bedrock model '$modelId' is not available in region '$region'.
AWS error: $modelJson

Action required:
  1. Enable model access in the Bedrock console for account $($identity.Account).
  2. Or verify the region is correct.
  3. Do not silently change the model ID. Report this blocker separately.
"@
    exit 1
}
$modelDetail = $modelJson | ConvertFrom-Json
Write-Host "Bedrock model available: $($modelDetail.modelDetails.modelId)"

# Step 6: GitHub environment protection check
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

# Step 7: Confirm existing variables and secrets are configured
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

foreach ($varName in @("AWS_REGION", "BEDROCK_MODEL_ID")) {
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

# Validate-only path
if (-not $Deploy) {
    Write-Host ""
    Write-Host "Validation complete. No AWS or GitHub changes were made."
    Write-Host "Run with -Deploy -Confirm to create the CloudFormation stack."
    exit 0
}

# Step 8: Require explicit confirmation
if (-not $Confirm) {
    Write-Error "Add -Confirm to acknowledge that AWS IAM resources will be created or updated."
    exit 1
}

# Step 9: Deploy CloudFormation stack
Write-Host ""
Write-Host "=== Deploying CloudFormation stack: $StackName ==="

$overrides = @(
    "ParameterKey=GitHubOrg,ParameterValue=ShieldTech-Ltd"
    "ParameterKey=GitHubRepo,ParameterValue=DUSK"
    "ParameterKey=GitHubEnvironment,ParameterValue=$GitHubEnvironment"
    "ParameterKey=BedrockModelId,ParameterValue=$modelId"
)
if ($ExistingOidcProviderArn) {
    $overrides += "ParameterKey=ExistingOidcProviderArn,ParameterValue=$ExistingOidcProviderArn"
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

# Step 10: Capture RoleArn output
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
Write-Host "Verify configuration: scripts/test-bedrock-oidc-config.ps1"
Write-Host ""
Write-Host "Next steps (manual, after PR is merged to main):"
Write-Host "  1. Trigger the workflow via GitHub Actions UI (requires ritiksah141 approval)."
Write-Host "  2. Do not dispatch automatically from this script."
