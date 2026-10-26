data "oci_core_images" "oracle_linux" {
  compartment_id           = var.compartment_id
  operating_system         = "Oracle Linux"
  operating_system_version = "9"
  shape                    = "VM.Standard.A1.Flex"
  sort_by                  = "TIMECREATED"
  sort_order               = "DESC"
}

resource "oci_core_vcn" "demo" {
  compartment_id = var.compartment_id
  cidr_blocks    = ["10.24.0.0/16"]
  display_name   = "dusk-public-demo"
  dns_label      = "duskdemo"
}

resource "oci_core_internet_gateway" "demo" {
  compartment_id = var.compartment_id
  vcn_id         = oci_core_vcn.demo.id
  display_name   = "dusk-public-demo"
  enabled        = true
}

resource "oci_core_route_table" "demo" {
  compartment_id = var.compartment_id
  vcn_id         = oci_core_vcn.demo.id
  display_name   = "dusk-public-demo"
  route_rules {
    destination       = "0.0.0.0/0"
    network_entity_id = oci_core_internet_gateway.demo.id
  }
}

resource "oci_core_security_list" "demo" {
  compartment_id = var.compartment_id
  vcn_id         = oci_core_vcn.demo.id
  display_name   = "dusk-public-demo"

  dynamic "ingress_security_rules" {
    for_each = toset([80, 443])
    content {
      protocol = "6"
      source   = "0.0.0.0/0"
      tcp_options {
        min = ingress_security_rules.value
        max = ingress_security_rules.value
      }
    }
  }

  egress_security_rules {
    protocol    = "all"
    destination = "0.0.0.0/0"
  }
}

resource "oci_core_subnet" "demo" {
  compartment_id    = var.compartment_id
  vcn_id            = oci_core_vcn.demo.id
  cidr_block        = "10.24.1.0/24"
  display_name      = "dusk-public-demo"
  dns_label         = "public"
  route_table_id    = oci_core_route_table.demo.id
  security_list_ids = [oci_core_security_list.demo.id]
}

resource "oci_core_instance" "demo" {
  availability_domain = var.availability_domain
  compartment_id      = var.compartment_id
  display_name        = "dusk-public-demo"
  shape               = "VM.Standard.A1.Flex"

  shape_config {
    ocpus         = var.instance_ocpus
    memory_in_gbs = var.instance_memory_gb
  }

  source_details {
    source_type             = "image"
    source_id               = data.oci_core_images.oracle_linux.images[0].id
    boot_volume_size_in_gbs = 100
  }

  create_vnic_details {
    subnet_id        = oci_core_subnet.demo.id
    assign_public_ip = true
    hostname_label   = "demo"
  }

  agent_config {
    are_all_plugins_disabled = false
    is_management_disabled   = false
    is_monitoring_disabled   = false
    plugins_config {
      name          = "Compute Instance Run Command"
      desired_state = "ENABLED"
    }
  }

  metadata = {
    user_data           = base64encode(file("${path.module}/../cloud-init.yaml"))
    ssh_authorized_keys = var.ssh_authorized_keys
  }

  lifecycle {
    precondition {
      condition     = var.ssh_authorized_keys == ""
      error_message = "Public-demo instances must not expose SSH. Use OCI Run Command for administration."
    }
  }
}

resource "oci_identity_dynamic_group" "demo_run_command" {
  compartment_id = var.tenancy_id
  name           = "dusk-public-demo-run-command"
  description    = "Only the DUSK public demo instance may execute OCI Run Commands"
  matching_rule  = "ALL {instance.id = '${oci_core_instance.demo.id}'}"
}

resource "oci_identity_policy" "demo_run_command" {
  compartment_id = var.compartment_id
  name           = "dusk-public-demo-run-command-agent"
  description    = "Allow the DUSK demo agent to poll and report its Run Commands"
  statements = [
    "Allow dynamic-group ${oci_identity_dynamic_group.demo_run_command.name} to use instance-agent-command-execution-family in compartment id ${var.compartment_id}",
  ]
}
