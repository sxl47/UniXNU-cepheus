#!/bin/bash
# Build the 64 MiB FAT16 cust-payload image for cepheus:
#   \EFI\UniXNU\unixnu.toml
#   \EFI\UniXNU\Payloads\kernel.macho        (XNU kernel, ~51 MiB)
#   \EFI\UniXNU\Payloads\kernel.macho.adt    (Apple Device Tree)
#   \EFI\UniXNU\Payloads\ramdisk.img         (empty 4 MiB FAT16 placeholder)
# UEFI (DarwinBoot) only mounts FAT volumes; Android partitions are ext4/f2fs,
# so without this image the firmware reports "no system found" and powers off.
# Flash target: the factory cust partition (expendable, not touched by MIUI boot).
#
# Usage: bash make-cepheus-cust-payload.sh <kernel.macho> <kernel.macho.adt> [output.img]
set -e
# Round 13 died silently inside this script on macOS: BSD dd rejects the GNU
# `status=none` operand (macOS runner), which set -e turns into a bare exit 1
# before the first echo. Trace everything, and keep brew's keg-only sbin
# (mkfs.vfat) on PATH for every step.
set -x
export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/local/sbin:$PATH"
K="${1:?kernel.macho}"
A="${2:?kernel.macho.adt}"
OUT="${3:-cust-payload.img}"
# Round 14: BSD readlink -f (macOS) refuses to resolve a path whose final
# component does not exist yet -- and $OUT is created later by dd. GNU
# readlink tolerates that, BSD does not, and set -e killed the script on the
# empty result. Resolve with plain $PWD instead; no readlink involved.
case "$OUT" in
  /*) OUT_ABS="$OUT" ;;
  *)  OUT_ABS="$PWD/$OUT" ;;
esac

STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT
mkdir -p "$STAGE/EFI/UniXNU/Payloads"
cp "$K" "$STAGE/EFI/UniXNU/Payloads/kernel.macho"
cp "$A" "$STAGE/EFI/UniXNU/Payloads/kernel.macho.adt"

# DarwinBoot refuses to boot (EFI_COMPROMISED_DATA, shown as "Compromised
# Data" on the menu) when the entry supplies an initrd but the ADT's
# /chosen/memory-map has no RAMDisk placeholder. The payload pipeline's ADT
# does not include one, so insert it here before packing the volume.
python3 "$(dirname "$0")/adt-add-ramdisk.py" \
  "$STAGE/EFI/UniXNU/Payloads/kernel.macho.adt" \
  "$STAGE/EFI/UniXNU/Payloads/kernel.macho.adt.new"
mv "$STAGE/EFI/UniXNU/Payloads/kernel.macho.adt.new" \
   "$STAGE/EFI/UniXNU/Payloads/kernel.macho.adt"

# A 4 MiB RAM disk: mockfs_mountroot needs a root vnode answering
# DKIOCGETMEMDEVINFO, and IOMedia only appears for a real device. Contents can
# stay empty for bring-up -- init will fail to find /sbin/launchd afterwards,
# which is the expected next step. The ADT is generated WITHOUT --data-ramdisk
# so its RAMDisk placeholder matches this empty image.
RAMDISK="$STAGE/EFI/UniXNU/Payloads/ramdisk.img"
if [ ! -f "$RAMDISK" ]; then
  dd if=/dev/zero of="$RAMDISK" bs=1048576 count=4 2>/dev/null
  if command -v mkfs.vfat >/dev/null 2>&1; then
    mkfs.vfat -F 16 -n CEPHRD "$RAMDISK" >/dev/null 2>&1 || true
  fi
fi
echo "ramdisk: $(stat -f %z "$RAMDISK" 2>/dev/null || stat -c %s "$RAMDISK" 2>/dev/null || echo 0) bytes"

# Boot arguments carried over from the nabu bring-up (same SM8150 platform):
#   -v serial=3 debug=0x14e   early kernel output
#   kextlog=0xfff             verbose kext logging
#   rd=ufsroot0               root on the raw UFS userdata partition via
#                             bsd/dev/cepheus_ufs.c (patch 0028); cepheus has
#                             no IOMedia class, so IOMedia UUID matching can
#                             never find a root candidate.
#   native-ufs-root=1         publish the UFS block class as the root device
#   sheng-data-persist=2      wait for store geometry so Data overlay activates
#   sheng-smp=0               single CPU for bring-up (SMP caused silent resets)
#   wdt=-1 / sheng-disable-watchdogd=1   keep watchdogs from biting
#   native-ufs-allow-unverified=1  adopt controller without verified-root bundle
#   kt_fixed_zones=120        fixed trace zone count, as sheng uses
#   -no_slto_panic            suppress the SLTO panic
#   amfi_get_out_of_my_way=1  payload is unsigned (diagnostic boot per docs)
cat > "$STAGE/EFI/UniXNU/unixnu.toml" <<'TOML'
version = 1

[boot]
# 0 = boot the default entry at once. The phone has no keyboard, and after
# one failed boot attempt Menu.c re-runs with Countdown=FALSE, which waits
# forever as soon as any input device is detected -- the menu then needs
# manual selection that is impossible without keys. Direct boot + a short
# fallback keeps unattended bring-up loops moving.
timeout = 3
fallback_timeout = 5
default = "xnu"

[kits]
autoload = false

[ui]
title = "UniXNU cepheus"
logo = true
console = "auto"

[[entry]]
id = "xnu"
title = "XNU (SM8150 UFS)"
type = "xnu"
path = "Payloads/kernel.macho"
initrd = "Payloads/ramdisk.img"
args = "-v serial=3 debug=0x14e kextlog=0xfff kt_fixed_zones=120 -no_slto_panic amfi_get_out_of_my_way=1 rd=ufsroot0 native-ufs-root=1 native-ufs-allow-unverified=1 sheng-data-persist=2 sheng-smp=0 wdt=-1 sheng-disable-watchdogd=1"
TOML

rm -f "$OUT"
dd if=/dev/zero of="$OUT" bs=1048576 count=64 2>/dev/null
mkfs.vfat -F 16 -n CEPHCUST "$OUT" > /dev/null
( cd "$STAGE" && mcopy -i "$OUT_ABS" -s EFI ::/ )

echo "=== contents verify ==="
mdir -i "$OUT_ABS" -/ ::/EFI/UniXNU/Payloads
ls -l "$OUT"
echo
echo "flash: fastboot flash cust $OUT"
