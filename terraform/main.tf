terraform {
  required_version = ">= 1.5.0"
  required_providers {
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = "~> 1.45"
    }
  }
}

provider "hcloud" {}

resource "hcloud_server" "app_server" {
  name        = "leadflow-cx23"
  server_type = "cx23"
  image       = "rocky-9"
  location    = "fsn1"

  lifecycle {
    prevent_destroy = true
    ignore_changes  = [user_data, ssh_keys, labels, placement_group_id]
  }
}
