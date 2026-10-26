variable "region" {
  description = "OCI region identifier"
  type        = string
}

variable "tenancy_id" {
  description = "Tenancy OCID used to create the instance Run Command dynamic group"
  type        = string
}

variable "compartment_id" {
  description = "Compartment OCID for the demo resources"
  type        = string
}

variable "availability_domain" {
  description = "Availability domain selected after checking A1 capacity"
  type        = string
}

variable "ssh_authorized_keys" {
  description = "Break-glass SSH keys. Leave empty to keep SSH unavailable."
  type        = string
  default     = ""
  sensitive   = true
}

variable "instance_ocpus" {
  description = "Ampere A1 OCPUs within the Always Free allocation"
  type        = number
  default     = 2
}

variable "instance_memory_gb" {
  description = "Ampere A1 memory in GB within the Always Free allocation"
  type        = number
  default     = 12
}
