#!/usr/bin/env python3
"""Insert a zeroed RAMDisk property into a DarwinBoot ADT.

DarwinBoot (DarwinBootPkg/Driver/DarwinBoot.c, check at the Request->Ramdisk
branch) requires /chosen/memory-map to carry a 16-byte "RAMDisk" property
(two u64 slots it fills with the ramdisk address and size) whenever the
boot entry supplies an initrd. Without it the boot returns
EFI_COMPROMISED_DATA ("Compromised Data" on the menu status line).

The ADT layout is the consecutive-children variant: node = (u32 nprops,
u32 nchildren, properties, children), no offset table. Property = 32-byte
name, u32 length, payload, 4-byte aligned.

Usage: adt-add-ramdisk.py <in.adt> <out.adt> [--force]
"""
import struct
import sys


def parse(data, off, depth, parent_path, tree):
    nprops = struct.unpack_from('<I', data, off)[0]
    nchildren = struct.unpack_from('<I', data, off + 4)[0]
    off += 8
    props = []
    name = None
    for _ in range(nprops):
        pname = data[off:off + 32].split(b'\0', 1)[0].decode('ascii', 'replace')
        length = struct.unpack_from('<I', data, off + 32)[0]
        off += 36
        payload = data[off:off + length]
        if pname == 'name':
            name = payload.split(b'\0', 1)[0].decode('ascii', 'replace')
        else:
            props.append((pname, payload))
        off += length
        off = (off + 3) & ~3
    path = 3
    if depth == 0:
        path = 0
    elif depth == 1 and parent_path == 0 and name == 'chosen':
        path = 1
    elif depth == 2 and parent_path == 1 and name == 'memory-map':
        path = 2
    children = []
    for _ in range(nchildren):
        off = parse(data, off, depth + 1, path, children)
    tree.append({'name': name, 'path': path, 'props': props, 'children': children})
    return off


def serialize(node):
    out = struct.pack('<II', len(node['props']), len(node['children']))
    out += struct.pack('<32sI', node['name'].encode(), 0)[:32] + b'\0' * 0
    # name property is stored with its payload length; rebuild exactly
    out = struct.pack('<II', len(node['props']) + 1, len(node['children']))
    out += struct.pack('<32sI', b'name', len(node['name']) + 1)
    out += node['name'].encode() + b'\0'
    out += b'\0' * ((4 - len(out) % 4) % 4)
    for pname, payload in node['props']:
        out += struct.pack('<32sI', pname.encode(), len(payload))
        out += payload
        out += b'\0' * ((4 - len(out) % 4) % 4)
    for child in node['children']:
        out += serialize(child)
    return out


def main():
    src, dst = sys.argv[1], sys.argv[2]
    force = '--force' in sys.argv
    data = open(src, 'rb').read()

    root = []
    end = parse(data, 0, 0, 3, root)
    assert end == len(data), f'ADT parse consumed {end} of {len(data)}'
    assert len(root) == 1
    root = root[0]

    # locate /chosen/memory-map
    chosen = [c for c in root['children'] if c['path'] == 1]
    assert len(chosen) == 1, f'expected one /chosen, got {len(chosen)}'
    maps = [c for c in chosen[0]['children'] if c['path'] == 2]
    assert len(maps) == 1, f'expected one /chosen/memory-map, got {len(maps)}'
    mmap = maps[0]

    existing = [p for p, _ in mmap['props'] if p in ('RAMDisk', 'PackedRAMDisk')]
    if existing and not force:
        print(f'RAMDisk already present ({existing}); nothing to do')
        open(dst, 'wb').write(data)
        return

    mmap['props'] = [(p, v) for p, v in mmap['props'] if p not in ('RAMDisk', 'PackedRAMDisk')]
    # 16 zero bytes: DarwinBoot fills address + size, and requires both to be 0
    mmap['props'].append(('RAMDisk', b'\0' * 16))

    out = serialize(root)
    # sanity: re-parse our own output and consume the full buffer
    check = []
    end2 = parse(out, 0, 0, 3, check)
    assert end2 == len(out), 're-parse failed'
    open(dst, 'wb').write(out)
    print(f'{src} ({len(data)} bytes) -> {dst} ({len(out)} bytes), RAMDisk property added')


if __name__ == '__main__':
    main()
