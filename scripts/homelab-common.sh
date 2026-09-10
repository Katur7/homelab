#!/usr/bin/env bash
# homelab-common.sh — Shared constants for homelab-up.sh and homelab-down.sh.

HOMELAB=/home/grimur/homelab
STATE_FILE=/var/lib/homelab-active-stacks

# Infrastructure stacks with ordering dependencies (must start in this order).
# All other infrastructure stacks are auto-discovered and have no ordering requirement.
INFRA_PRIORITY=(gateway dns cloudflare)
