output "instance_id" {
  description = "Instance OCID used by the deployment workflow"
  value       = oci_core_instance.demo.id
}

output "public_ip" {
  description = "Public address for the three demo DNS records"
  value       = oci_core_instance.demo.public_ip
}

output "compartment_id" {
  description = "Compartment OCID used by OCI Run Command"
  value       = var.compartment_id
}
