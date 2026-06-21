# OCI Homelab - Main Terraform Configuration
# Provisions networking, security, and a single ARM-based compute instance

terraform {
  required_providers {
    oci = {
      source  = "oracle/oci"
      version = "~> 5.0"
    }
  }
}

# ---------------------------------------------------------------------------
# Provider — credentials injected via variables (from GitHub Secrets / tfvars)
# ---------------------------------------------------------------------------
provider "oci" {
  tenancy_ocid = var.tenancy_ocid
  user_ocid    = var.user_ocid
  fingerprint  = var.fingerprint
  private_key  = var.private_key
  region       = var.region
}


# ---------------------------------------------------------------------------
# Ubuntu 20.04 ARM (aarch64) — Canonical image
# ---------------------------------------------------------------------------
data "oci_core_images" "ubuntu_arm" {
  compartment_id           = var.tenancy_ocid
  operating_system         = "Canonical Ubuntu"
  operating_system_version = "20.04"
  shape                    = "VM.Standard.A2.Flex"
  sort_by                  = "TIMECREATED"
  sort_order               = "DESC"

  filter {
    name   = "display_name"
    values = [".*aarch64.*"]
    regex  = true
  }
}

# ---------------------------------------------------------------------------
# Virtual Cloud Network
# ---------------------------------------------------------------------------
resource "oci_core_vcn" "homelab_vcn" {
  compartment_id = var.tenancy_ocid
  cidr_block     = "10.0.0.0/16"
  display_name   = "homelab-vcn"
  dns_label      = "homelabvcn"
}

# ---------------------------------------------------------------------------
# Internet Gateway
# ---------------------------------------------------------------------------
resource "oci_core_internet_gateway" "homelab_igw" {
  compartment_id = var.tenancy_ocid
  vcn_id         = oci_core_vcn.homelab_vcn.id
  display_name   = "homelab-igw"
  enabled        = true
}

# ---------------------------------------------------------------------------
# Route Table — default route via Internet Gateway
# ---------------------------------------------------------------------------
resource "oci_core_route_table" "homelab_rt" {
  compartment_id = var.tenancy_ocid
  vcn_id         = oci_core_vcn.homelab_vcn.id
  display_name   = "homelab-route-table"

  route_rules {
    destination       = "0.0.0.0/0"
    network_entity_id = oci_core_internet_gateway.homelab_igw.id
  }
}

# ---------------------------------------------------------------------------
# Security List — opens required ingress ports + allows all egress
# ---------------------------------------------------------------------------
resource "oci_core_security_list" "homelab_sl" {
  compartment_id = var.tenancy_ocid
  vcn_id         = oci_core_vcn.homelab_vcn.id
  display_name   = "homelab-security-list"

  # Allow all outbound traffic
  egress_security_rules {
    destination = "0.0.0.0/0"
    protocol    = "all"
  }

  # SSH
  ingress_security_rules {
    protocol = "6" # TCP
    source   = "0.0.0.0/0"
    tcp_options {
      min = 22
      max = 22
    }
  }

  # Airflow Webserver
  ingress_security_rules {
    protocol = "6"
    source   = "0.0.0.0/0"
    tcp_options {
      min = 8080
      max = 8080
    }
  }

  # General application port
  ingress_security_rules {
    protocol = "6"
    source   = "0.0.0.0/0"
    tcp_options {
      min = 8000
      max = 8000
    }
  }

  # Node / frontend dev port
  ingress_security_rules {
    protocol = "6"
    source   = "0.0.0.0/0"
    tcp_options {
      min = 3000
      max = 3000
    }
  }

  # PostgreSQL
  ingress_security_rules {
    protocol = "6"
    source   = "0.0.0.0/0"
    tcp_options {
      min = 5432
      max = 5432
    }
  }
}

# ---------------------------------------------------------------------------
# Public Subnet
# ---------------------------------------------------------------------------
resource "oci_core_subnet" "homelab_subnet" {
  compartment_id    = var.tenancy_ocid
  vcn_id            = oci_core_vcn.homelab_vcn.id
  cidr_block        = "10.0.1.0/24"
  display_name      = "homelab-public-subnet"
  dns_label         = "homelabsubnet"
  route_table_id    = oci_core_route_table.homelab_rt.id
  security_list_ids = [oci_core_security_list.homelab_sl.id]

  # Public subnet — instances get a public IP automatically
  prohibit_public_ip_on_vnic = false
}

# ---------------------------------------------------------------------------
# Compute Instance — VM.Standard.A2.Flex (ARM, Paid tier with $300 credits)
# ---------------------------------------------------------------------------
resource "oci_core_instance" "homelab_vm" {
  compartment_id      = var.tenancy_ocid
  availability_domain = var.availability_domain
  fault_domain        = var.fault_domain
  display_name        = var.instance_display_name
  shape               = "VM.Standard.A2.Flex"

  shape_config {
    ocpus         = var.ocpus
    memory_in_gbs = var.memory_in_gbs
  }

  source_details {
    source_type             = "image"
    source_id               = var.ubuntu_image_id
    boot_volume_size_in_gbs = var.boot_volume_size_in_gbs
  }

  create_vnic_details {
    subnet_id        = oci_core_subnet.homelab_subnet.id
    assign_public_ip = true
    display_name     = "homelab-vnic"
  }

  launch_options {
    network_type                        = "PARAVIRTUALIZED"
    remote_data_volume_type             = "PARAVIRTUALIZED"
    boot_volume_type                    = "PARAVIRTUALIZED"
    firmware                            = "UEFI_64"
    is_pv_encryption_in_transit_enabled = true
  }

  metadata = {
    ssh_authorized_keys = var.ssh_public_key
    # cloud-init script is base64-encoded so OCI can pass it verbatim
    user_data = base64encode(file("${path.module}/cloud-init.yaml"))
  }

  lifecycle {
    ignore_changes = [source_details[0].source_id]
  }
}

# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------
output "public_ip" {
  description = "Public IP address of the homelab VM"
  value       = oci_core_instance.homelab_vm.public_ip
}

output "ssh_command" {
  description = "Ready-to-use SSH command"
  value       = "ssh ubuntu@${oci_core_instance.homelab_vm.public_ip}"
}

output "airflow_url" {
  description = "Airflow web UI URL"
  value       = "http://${oci_core_instance.homelab_vm.public_ip}:8080"
}
