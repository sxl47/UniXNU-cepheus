#!/usr/bin/env python3
"""Generate the minimal cepheus (Xiaomi Mi 9, SM8150) hardware Apple-format DT.

Derived from Lux12138/UniXNU scripts/make-nabu-adt.py (itself derived from
make-sheng-adt.py). The SM8150 platform values are shared with nabu:

  - GICv3 distributor 0x17a00000/0x10000, redistributor 0x17a60000/0x100000
    (arm-io child offsets under an APSS range at 0x17000000), stride 0x40000
  - CPU timebase 19200000 Hz (Qualcomm SM8xxx architectural counter)
  - DRAM base 0x80000000; size must come from the actual device observation
  - UFS HC 0x1d84000; NativeUfs takes physical windows from its own constants

cepheus additions over nabu:

  - /cepheus-fbcon node consumed by patch 0003 (framebuffer serial console):
    reg = <phys size> absolute physical address of the MDSS framebuffer,
    width/height/stride (32bpp). The defaults below are NABU placeholders
    (0x9C000000/0xC00000, 1080x2340, 4320) -- TODO_MEASURE: read the real
    cepheus values from the device tree of the Mi 9 boot image and pass
    --fbcon-reg/--fbcon-size or edit the defaults here.

This is first-boot bring-up data: the platform has no matching platform
expert yet, so the kernel is expected to reach the video console and report
the genuine missing-driver panic on screen. No Apple device identity is
claimed and no property is invented beyond these pinned sources.
"""
from pathlib import Path
import argparse
import os
import struct
import zlib

ROOT = Path(__file__).resolve().parents[1]

DRAM_BASE = 0x80000000
ARMIO_BASE = 0x17000000          # APSS peripheral block containing the GIC
GIC_DIST = 0x17a00000            # SM8150: sm8150.dtsi intc@17a00000
GIC_DIST_SIZE = 0x10000
GIC_REDIST = 0x17a60000          # SM8150: GICR * 8
GIC_REDIST_SIZE = 0x100000
TIMEBASE = 19200000
UFS_HC = 0x1d84000               # SM8150 ufshc@1d84000 (identical on SM8550)
UFS_HC_SIZE = 0x3000

# TODO_MEASURE: nabu placeholders. Mi 9 panel: Samsung s6e3fc2x01, 1080x2340.
# The physical framebuffer address/size must be taken from the cepheus DT.
FBCON_REG_DEFAULT = 0x9C000000
FBCON_SIZE_DEFAULT = 0xC00000
FBCON_WIDTH_DEFAULT = 1080
FBCON_HEIGHT_DEFAULT = 2340
FBCON_STRIDE_DEFAULT = 4320


def node(name, properties=(), children=()):
    properties = [('name', name.encode() + b'\0'), *properties]
    result = struct.pack('<II', len(properties), len(children))
    for key, data in properties:
        result += struct.pack('<32sI', key.encode(), len(data))
        result += data + bytes(-len(data) % 4)
    return result + b''.join(children)


def empty_nvram_proxy():
    """A fresh volatile CHRP bank for upstream IODTNVRAM, with no controller."""
    def header(name, size):
        raw = bytearray(struct.pack('<BBH12s', 0x70, 0, size // 16, name))
        checksum = sum(raw)
        while checksum > 255:
            checksum = (checksum & 255) + (checksum >> 8)
        raw[1] = checksum
        return raw

    image = bytearray(8192)
    image[:16] = header(b'nvram', 32)
    image[32:48] = header(b'common', 16 + 2048)
    free_at = 32 + 16 + 2048
    image[free_at:free_at + 16] = header(b'free', len(image) - free_at)
    struct.pack_into('<I', image, 16, zlib.adler32(image[20:]))
    return [('nvram-bank-size', struct.pack('<I', len(image))),
            ('nvram-bank-count', struct.pack('<I', 1)),
            ('nvram-current-bank', struct.pack('<I', 0)),
            ('nvram-proxy-data', bytes(image))]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path,
                        default=ROOT / 'build/cepheus/boot/kernel.macho.adt')
    parser.add_argument('--dram-size', type=lambda value: int(value, 0), required=True,
                        help='Actual observed DRAM size, e.g. 0x1C0000000 for 7 GiB')
    parser.add_argument('--owned-memory-size', type=lambda value: int(value, 0), default=None,
                        help='Explicit DarwinBoot contiguous window request, 256 MiB..8 GiB in 2 MiB steps')
    parser.add_argument('--root-match-volume-uuid', default=None,
                        help='/chosen/root-matching: select the root by the UUID of an IOMedia')
    parser.add_argument('--unique-chip-id', type=lambda value: int(value, 16), default=None,
                        help='/chosen/unique-chip-id (8 bytes)')
    parser.add_argument('--chip-id', type=lambda value: int(value, 16), default=None)
    parser.add_argument('--ipad-identity', action='store_true',
                        help='/product and /buttons describe an iPad-class device without a Home button')
    parser.add_argument('--cpu-regs', default='0',
                        help='Comma-separated CPU MPIDR affinity values; SM8150 numbers cores 0x000..0x700 in Affinity1')
    parser.add_argument('--psci-method', choices=['smc', 'hvc'], default='smc')
    parser.add_argument('--packed-data-ramdisk', action='store_true')
    parser.add_argument('--data-ramdisk', action='store_true')
    parser.add_argument('--trust-cache', action='store_true')
    parser.add_argument('--fbcon-reg', type=lambda value: int(value, 0), default=FBCON_REG_DEFAULT,
                        help='TODO_MEASURE: physical framebuffer address (patch 0003 /cepheus-fbcon)')
    parser.add_argument('--fbcon-size', type=lambda value: int(value, 0), default=FBCON_SIZE_DEFAULT,
                        help='TODO_MEASURE: framebuffer mapping size in bytes')
    parser.add_argument('--fbcon-width', type=int, default=FBCON_WIDTH_DEFAULT)
    parser.add_argument('--fbcon-height', type=int, default=FBCON_HEIGHT_DEFAULT)
    parser.add_argument('--fbcon-stride', type=int, default=FBCON_STRIDE_DEFAULT)
    args = parser.parse_args()
    if (args.unique_chip_id is None) != (args.chip_id is None):
        parser.error('--unique-chip-id and --chip-id must be supplied together')
    if args.unique_chip_id is not None and not (0 < args.unique_chip_id < 1 << 64 and 0 < args.chip_id < 1 << 32):
        parser.error('--unique-chip-id must fit 8 bytes and --chip-id 4 bytes, both nonzero')
    if args.owned_memory_size is not None and (
            not 0x10000000 <= args.owned_memory_size <= 0x200000000
            or args.owned_memory_size % 0x200000):
        parser.error('Owned memory must be 256 MiB to 8 GiB, aligned to 2 MiB')

    try:
        cpu_regs = [int(value, 0) for value in args.cpu_regs.split(',')]
    except ValueError:
        parser.error('--cpu-regs must be integers')
    if (not cpu_regs or cpu_regs[0] != 0 or len(set(cpu_regs)) != len(cpu_regs) or len(cpu_regs) > 8
            or any(reg < 0 or reg > 0xffff or reg & 0xff for reg in cpu_regs)):
        parser.error('--cpu-regs: up to eight distinct Affinity1-numbered cores, boot CPU 0 first')
    cpus = [node('cpu%d' % index, [('state', b'running\0' if index == 0 else b'waiting\0'),
                                   ('reg', struct.pack('<I', reg)),
                                   ('device_type', b'cpu\0'), ('compatible', b'arm,cortex-a76\0'),
                                   ('timebase-frequency', struct.pack('<I', TIMEBASE))])
            for index, reg in enumerate(cpu_regs)]
    tree = node('device-tree', [
        ('model', b'iPad7,1\0' if args.ipad_identity else b'cepheus-first-boot\0'),
        *([('target-type', b'J120\0')] if args.ipad_identity else []),
        # Root compatible strings: cepheus board DT is xiaomi,cepheus / qcom,sm8150.
        ('compatible', b'xiaomi,cepheus\0qcom,sm8150\0'),
        ('#address-cells', struct.pack('<I', 2)),
        ('#size-cells', struct.pack('<I', 2)),
    ], [
        node('chosen', [('random-seed', os.urandom(64)),
                        *([('unique-chip-id', struct.pack('<Q', args.unique_chip_id)), ('chip-id', struct.pack('<I', args.chip_id))]
                          if args.unique_chip_id is not None else []),
                        # pe_kprintf.c defaults disable_kprintf_output to true and only
                        # clears it when -enable_kprintf_spam is present in boot-args.
                        # Without this property the kernel prints nothing at all and
                        # the boot log is invisible by design.
        ('boot-args', b'-enable_kprintf_spam rd=ufsroot0\0'),
                        ('osenvironment', b'main\0'),
                        *([('certificate-production-status', struct.pack('<I', 0)), ('effective-production-status-ap', struct.pack('<I', 0)),
                           ('certificate-security-mode', struct.pack('<I', 1)), ('effective-security-mode-sep', struct.pack('<I', 1))]
                          if args.ipad_identity else []),
                        *([('ephemeral-storage', struct.pack('<I', 1))] if (args.data_ramdisk or args.packed_data_ramdisk) else []),
                        *( [('darwinboot-memory-size', struct.pack('<Q', args.owned_memory_size))]
                           if args.owned_memory_size else [] ),
                        ('dram-base', struct.pack('<Q', DRAM_BASE)),
                        ('dram-size', struct.pack('<Q', args.dram_size)),
                        ('crypto-hash-method', b'sha2-384\0'),
                        *( [('root-matching', ('<dict><key>IOProviderClass</key><string>IOMedia</string>'
                                               '<key>IOPropertyMatch</key><dict><key>UUID</key><string>' +
                                               args.root_match_volume_uuid.upper() + '</string></dict></dict>\0').encode())]
                           if args.root_match_volume_uuid else [] ),
                        ('amfi-only-platform-code', struct.pack('<I', 1)),
                        *empty_nvram_proxy()],
             [node('memory-map', ([("PackedRAMDisk" if args.packed_data_ramdisk else "RAMDisk", bytes(16))] if (args.data_ramdisk or args.packed_data_ramdisk) else []) +
                                 ([('TrustCache', bytes(16))] if args.trust_cache else [])),
              node('manifest-properties')]),
        node('cpus', children=cpus),
        *([node('psci', [('compatible', b'arm,psci-1.0\0'), ('method', args.psci_method.encode() + b'\0')])] if len(cpus) > 1 else []),
        node('defaults', [('sleep-disabled', struct.pack('<I', 1))]),
        node('options', []),
        # Consumed by patch 0003 (framebuffer serial console). Values are
        # TODO_MEASURE nabu placeholders until the cepheus DT is read.
        node('cepheus-fbcon', [
            ('reg', struct.pack('<QQ', args.fbcon_reg, args.fbcon_size)),
            ('width', struct.pack('<I', args.fbcon_width)),
            ('height', struct.pack('<I', args.fbcon_height)),
            ('stride', struct.pack('<I', args.fbcon_stride)),
        ]),
        # Consumed by bsd/dev/cepheus_ufs.c (patch 0028): the raw UFS root
        # driver maps its register window from this node. reg = <phys size>
        # of the SM8150 UFS host controller (same constants as NativeUfs).
        node('cepheus-ufs', [
            ('reg', struct.pack('<QQ', UFS_HC, UFS_HC_SIZE)),
        ]),
        *( [node('buttons', [('compatible', b'buttons\0'), ('device_type', b'buttons\0'),
                             ('button-names', b'hold\0voldown\0volup\0'),
                             ('home-button-type', struct.pack('<I', 2))])] if args.ipad_identity else [] ),
        node('product', [('product-name', b'iPad Pro (12.9-inch) (2nd generation)\0' if args.ipad_identity else b'Xiaomi Mi 9\0'),
                         ('model', b'xiaomi,cepheus\0'),
                         *( [('product-description', b'iPad Pro (12.9-inch) (2nd generation)\0'),
                             ('artwork-device-idiom', b'pad\0'),
                             ('artwork-device-subtype', struct.pack('<I', 2732)),
                             ('artwork-scale-factor', struct.pack('<I', 2)),
                             ('artwork-display-gamut', b'P3\0'),
                             ('compatible-device-fallback', b'iPad6,7\0'),
                             ('thin-bezel', struct.pack('<I', 1))] if args.ipad_identity else [] )]),
        node('arm-io', [('device_type', b'arm-io\0'),
                        ('#address-cells', struct.pack('<I', 2)),
                        ('#size-cells', struct.pack('<I', 2)),
                        ('ranges', struct.pack('<QQQ', 0, ARMIO_BASE, 0x08000000))],
             [node('intc', [('compatible', b'arm,gic-v3\0'),
                            ('reg', struct.pack('<4Q',
                                                GIC_DIST - ARMIO_BASE, GIC_DIST_SIZE,
                                                GIC_REDIST - ARMIO_BASE, GIC_REDIST_SIZE)),
                            ('redistributor-stride', struct.pack('<Q', 0x40000))]),
              # UFS (0x1d84000) lies below the arm-io window, so a child reg offset would be
              # negative. The node exists only for class matching; NativeUfs takes its
              # physical windows from the board DT constants.
              node('ufshc', [('compatible', b'qcom,sm8150-ufshc\0')])]),
    ])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(tree)
    print(f'cepheus ADT: {len(tree)} bytes, dram {args.dram_size:#x}, '
          f'fbcon {args.fbcon_reg:#x}/{args.fbcon_width}x{args.fbcon_height}, timebase {TIMEBASE}')


if __name__ == '__main__':
    main()
