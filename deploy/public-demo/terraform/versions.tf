terraform {
  required_version = ">= 1.8.0"

  # Supply bucket, namespace, region, and key during `terraform init`. Keeping
  # the backend partial prevents account identifiers and credentials from
  # being committed while still forbidding accidental local state.
  backend "oci" {}

  required_providers {
    oci = {
      source  = "oracle/oci"
      version = "~> 7.0"
    }
  }
}

provider "oci" {
  region = var.region
}
