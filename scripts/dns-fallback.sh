#!/bin/bash
# Minimal, safe DNS integration for OpenVPN when the
# systemd-resolved plugin or helper scripts are unavailable.
#
# Works with systemd-resolved via `resolvectl`.
#
# Usage: invoked by OpenVPN as --up/--down script. It relies on
# environment variables set by OpenVPN (script_type, dev, foreign_option_*).

set -euo pipefail

log() {
  # Log to stdout; OpenVPN's stdout is captured by the GUI helper.
  echo "[dns-fallback] $*"
}

die() {
  echo "[dns-fallback][ERROR] $*" >&2
  exit 1
}

have_cmd() {
  command -v "$1" >/dev/null 2>&1
}

# Determine script type (up/down) in a robust way
SCRIPT_TYPE="${script_type:-}"
if [ -z "$SCRIPT_TYPE" ] && [ $# -gt 0 ]; then
  # Some setups pass the type as first arg
  case "$1" in
    up|down)
      SCRIPT_TYPE="$1" ;;
  esac
fi
[ -n "$SCRIPT_TYPE" ] || die "script_type not provided by OpenVPN"

# Interface name provided by OpenVPN
OVPN_DEV="${dev:-}"
[ -n "$OVPN_DEV" ] || die "OpenVPN did not export 'dev'"

# Prefer resolvectl
if have_cmd resolvectl; then
  RESOLVCTL="resolvectl"
elif have_cmd systemd-resolve; then
  RESOLVCTL="systemd-resolve"
else
  die "Neither resolvectl nor systemd-resolve found; cannot safely configure DNS"
fi

# Helper: extract DNS servers from foreign_option_* env vars
extract_dns_servers() {
  local dns_list=()
  # Iterate over exported env names matching foreign_option_*
  # shellcheck disable=SC2048,SC2086
  for name in $(env | awk -F= '/^foreign_option_[0-9]+=/{ print $1 }'); do
    val="${!name}"
    # Normalize multiple spaces
    val="$(echo "$val" | tr -s ' ')"
    # Expect patterns like: 'dhcp-option DNS 10.0.0.1'
    if echo "$val" | grep -qiE '^dhcp-option[[:space:]]+DNS[[:space:]]+'; then
      # Get the token after 'DNS'
      dns="$(echo "$val" | awk 'BEGIN{IGNORECASE=1} $1=="dhcp-option" && $2=="DNS" {print $3}')"
      if [ -n "$dns" ]; then dns_list+=("$dns"); fi
    fi
  done
  printf '%s\n' "${dns_list[@]}"
}

setup_resolved() {
  local dev="$1"; shift
  local -a dns_servers=("$@")

  if [ ${#dns_servers[@]} -eq 0 ]; then
    log "No DNS servers received from VPN; leaving system DNS unchanged"
    return 0
  fi

  # Configure DNS servers on the interface
  log "Setting DNS on $dev: ${dns_servers[*]}"
  $RESOLVCTL dns "$dev" "${dns_servers[@]}" || die "Failed to set DNS via $RESOLVCTL"

  # Route all domains through this link (default DNS route)
  # Using '~.' to mark as routing-only domain for all queries.
  if $RESOLVCTL domain "$dev" '~.'; then
    log "Set domain routing '~.' on $dev"
  else
    log "Warning: failed to set domain '~.' on $dev"
  fi

  # Optional: mark as default route for DNS if supported (resolvectl >= 249)
  if $RESOLVCTL help 2>/dev/null | grep -q "default-route"; then
    $RESOLVCTL default-route "$dev" yes || true
  fi

  # Optional hardening: proactively prevent DNS leaks on non-tun interfaces
  # Enable with OPENVPN_PY_ENFORCE_DNS_BLACKHOLE=1
  if [ "${OPENVPN_PY_ENFORCE_DNS_BLACKHOLE:-0}" = "1" ]; then
    # Try nft first, fallback to iptables. Rules are namespaced with a comment for cleanup.
    if have_cmd nft; then
      # Create a dedicated chain in the output hook (inet table) to drop DNS except on the VPN device
      nft list table inet openvpn_py 2>/dev/null || nft add table inet openvpn_py
      nft list chain inet openvpn_py dns_guard 2>/dev/null || nft add chain inet openvpn_py dns_guard '{ type filter hook output priority 0; policy accept; }'
      nft add rule inet openvpn_py dns_guard meta oifname != "$dev" udp dport 53 counter drop comment "openvpn-py-dns"
      nft add rule inet openvpn_py dns_guard meta oifname != "$dev" tcp dport 53 counter drop comment "openvpn-py-dns"
      log "Installed nftables DNS guard (drop TCP/UDP 53 outside $dev)"
    elif have_cmd iptables && have_cmd ip6tables; then
      # Legacy iptables rules
      iptables -I OUTPUT -p udp --dport 53 ! -o "$dev" -m comment --comment openvpn-py-dns -j DROP || true
      iptables -I OUTPUT -p tcp --dport 53 ! -o "$dev" -m comment --comment openvpn-py-dns -j DROP || true
      ip6tables -I OUTPUT -p udp --dport 53 ! -o "$dev" -m comment --comment openvpn-py-dns -j DROP || true
      ip6tables -I OUTPUT -p tcp --dport 53 ! -o "$dev" -m comment --comment openvpn-py-dns -j DROP || true
      log "Installed iptables DNS guard (drop TCP/UDP 53 outside $dev)"
    else
      log "DNS blackhole requested, but neither nft nor (ip|ip6)tables are available"
    fi
  fi
}

cleanup_resolved() {
  local dev="$1"
  log "Reverting DNS settings on $dev"
  $RESOLVCTL revert "$dev" || true

  # Remove optional DNS blackhole
  if [ "${OPENVPN_PY_ENFORCE_DNS_BLACKHOLE:-0}" = "1" ]; then
    if have_cmd nft; then
      # Flush rules with our comment, then drop table if empty
      nft list chain inet openvpn_py dns_guard 2>/dev/null | grep -q openvpn-py-dns && nft flush chain inet openvpn_py dns_guard || true
      # Best-effort table removal if empty
      nft list table inet openvpn_py >/dev/null 2>&1 && nft delete table inet openvpn_py >/dev/null 2>&1 || true
      log "Removed nftables DNS guard"
    elif have_cmd iptables && have_cmd ip6tables; then
      while iptables -D OUTPUT -p udp --dport 53 ! -o "$dev" -m comment --comment openvpn-py-dns -j DROP 2>/dev/null; do :; done
      while iptables -D OUTPUT -p tcp --dport 53 ! -o "$dev" -m comment --comment openvpn-py-dns -j DROP 2>/dev/null; do :; done
      while ip6tables -D OUTPUT -p udp --dport 53 ! -o "$dev" -m comment --comment openvpn-py-dns -j DROP 2>/dev/null; do :; done
      while ip6tables -D OUTPUT -p tcp --dport 53 ! -o "$dev" -m comment --comment openvpn-py-dns -j DROP 2>/dev/null; do :; done
      log "Removed iptables DNS guard"
    fi
  fi
}

case "$SCRIPT_TYPE" in
  up)
    # Delay briefly to ensure the link is created
    sleep 0.2 || true
    mapfile -t DNS_SERVERS < <(extract_dns_servers)
    setup_resolved "$OVPN_DEV" "${DNS_SERVERS[@]:-}"
    ;;
  down)
    cleanup_resolved "$OVPN_DEV"
    ;;
  *)
    log "Unknown script_type '$SCRIPT_TYPE' (no-op)"
    ;;
esac

exit 0

