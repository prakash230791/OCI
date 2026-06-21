# OCI Homelab - Variable Definitions (Paid Tier)
# All values are supplied at runtime via terraform.tfvars
# No defaults are set — a missing value will cause Terraform to error early and clearly.

# ============================================================================
# OCI Authentication & Tenancy
# ============================================================================

variable "tenancy_ocid" {
  description = "OCID of the OCI tenancy (root compartment). Found in OCI Console → Profile → Tenancy."
  type        = string
  sensitive   = true
}

variable "user_ocid" {
  description = "OCID of the OCI IAM user whose API key is used. Found in OCI Console → Profile → My Profile."
  type        = string
  sensitive   = true
}

variable "fingerprint" {
  description = "MD5 fingerprint of the API key uploaded to the OCI user. Found in OCI Console → My Profile → API Keys."
  type        = string
  sensitive   = true
}

variable "private_key" {
  description = "PEM-formatted RSA private key that corresponds to the uploaded API key fingerprint."
  type        = string
  sensitive   = true
}

variable "region" {
  description = "OCI region identifier, e.g. us-ashburn-1. Found in OCI Console top-right region selector."
  type        = string
}

# ============================================================================
# SSH Access
# ============================================================================

variable "ssh_public_key" {
  description = "SSH public key (ed25519 or RSA) to inject into the instance for ubuntu user login."
  type        = string
}

# ============================================================================
# Compute Instance Configuration
# ============================================================================

variable "availability_domain" {
  description = "Availability domain in full format, e.g., 'nhrz:US-ASHBURN-AD-1'"
  type        = string
}

variable "fault_domain" {
  description = "Fault domain, e.g., 'FAULT-DOMAIN-3'"
  type        = string
  default     = "FAULT-DOMAIN-3"
}

variable "instance_display_name" {
  description = "Display name for the compute instance, e.g., 'instance-20260621-1000'"
  type        = string
  default     = "homelab-vm"
}

variable "ocpus" {
  description = "Number of OCPUs for VM.Standard.A2.Flex shape"
  type        = number
  default     = 2
}

variable "memory_in_gbs" {
  description = "Memory in GB for VM.Standard.A2.Flex shape"
  type        = number
  default     = 12
}

# ============================================================================
# Image Configuration
# ============================================================================

variable "ubuntu_image_id" {
  description = "OCID of the Ubuntu 20.04 ARM (aarch64) image. Found in OCI Console → Images."
  type        = string
  sensitive   = false
}

variable "boot_volume_size_in_gbs" {
  description = "Boot volume size in GB"
  type        = number
  default     = 100
}
