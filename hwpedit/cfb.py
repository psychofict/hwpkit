"""Minimal MS-CFB rewriter for HWP 5.0 files.

Reads an existing CFB compound file with olefile, lets the caller replace
specific streams, and writes a new compound file that preserves the
original directory tree topology (sid_left, sid_right, sid_child, color,
clsid, timestamps) so Hancom's strict tree-validation logic keeps working.

See docs/GOTCHAS.md for why rebuilding the directory tree from scratch
typically fails Hancom's validation.
"""

from __future__ import annotations

import struct
import olefile

SECTORSIZE = 512
MINISECTORSIZE = 64
MINISTREAM_CUTOFF = 4096
FAT_ENTRIES_PER_SECTOR = SECTORSIZE // 4
MINIFAT_ENTRIES_PER_SECTOR = SECTORSIZE // 4
DIR_ENTRIES_PER_SECTOR = SECTORSIZE // 128
HEADER_DIFAT_COUNT = 109
DIFAT_ENTRIES_PER_SECTOR = (SECTORSIZE // 4) - 1  # last 4 bytes = next DIFAT sector

MAXREGSECT = 0xFFFFFFFA
DIFSECT = 0xFFFFFFFC
FATSECT = 0xFFFFFFFD
ENDOFCHAIN = 0xFFFFFFFE
FREESECT = 0xFFFFFFFF
NOSTREAM = 0xFFFFFFFF

CFB_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


class DirEntryOut:
    __slots__ = (
        "name", "etype", "color", "left", "right", "child",
        "clsid", "state_bits", "ctime", "mtime", "start_sect", "size",
        "data",
    )

    def __init__(self, name, etype, color, left, right, child,
                 clsid, state_bits, ctime, mtime, data):
        self.name = name
        self.etype = etype
        self.color = color
        self.left = left
        self.right = right
        self.child = child
        self.clsid = clsid
        self.state_bits = state_bits
        self.ctime = ctime
        self.mtime = mtime
        self.start_sect = 0
        self.size = 0
        self.data = data  # bytes for streams, None for storages


def _read_dir_raw(ole):
    """Pull raw 128-byte directory records from the original file so we
    preserve fields olefile doesn't expose (state_bits, timestamps, raw clsid).
    Returns a dict: sid -> raw 128-byte record.
    """
    fp = ole.fp
    sect = ole.first_dir_sector
    raw_dir = bytearray()
    visited = set()
    while sect != ENDOFCHAIN and sect <= MAXREGSECT:
        if sect in visited:
            raise RuntimeError("directory chain loop")
        visited.add(sect)
        fp.seek((sect + 1) * ole.sectorsize)
        raw_dir.extend(fp.read(ole.sectorsize))
        sect = ole.fat[sect]
    entries = {}
    for sid in range(len(raw_dir) // 128):
        entries[sid] = bytes(raw_dir[sid * 128 : (sid + 1) * 128])
    return entries


def load(path: str):
    """Load a CFB into a dict of sid -> DirEntryOut, preserving tree topology.
    Stream data is in entry.data; storages have data=None.
    """
    ole = olefile.OleFileIO(path)
    raw = _read_dir_raw(ole)
    entries = {}
    for de in ole.direntries:
        if de is None:
            continue
        sid = de.sid
        raw_entry = raw.get(sid, b"\x00" * 128)
        clsid_bytes = raw_entry[80:96]
        state_bits = raw_entry[96:100]
        ctime = raw_entry[100:108]
        mtime = raw_entry[108:116]
        name_len = struct.unpack("<H", raw_entry[64:66])[0]
        if name_len > 64:
            name_len = 64
        name_utf16 = raw_entry[0 : max(0, name_len - 2)]
        try:
            name = name_utf16.decode("utf-16-le")
        except UnicodeDecodeError:
            name = de.name
        if de.entry_type == 2 and de.size > 0:
            path_parts = _path_for_sid(ole, sid)
            data = ole.openstream(path_parts).read()
        else:
            data = None
        entries[sid] = DirEntryOut(
            name=name,
            etype=de.entry_type,
            color=de.color,
            left=de.sid_left if de.sid_left is not None else NOSTREAM,
            right=de.sid_right if de.sid_right is not None else NOSTREAM,
            child=de.sid_child if de.sid_child is not None else NOSTREAM,
            clsid=clsid_bytes,
            state_bits=state_bits,
            ctime=ctime,
            mtime=mtime,
            data=data,
        )
    ole.close()
    return entries


def _path_for_sid(ole, sid):
    """Return olefile-style path list for a given sid by walking from root."""
    target_de = next(d for d in ole.direntries if d is not None and d.sid == sid)
    path = [target_de.name]

    def find_parent(de):
        for cand in ole.direntries:
            if cand is None:
                continue
            if cand.kids and any(k.sid == de.sid for k in cand.kids):
                return cand
        return None

    cur = target_de
    while True:
        parent = find_parent(cur)
        if parent is None or parent.sid == 0:
            break
        path.insert(0, parent.name)
        cur = parent
    return path


def dump(entries, out_path, target_sid_to_replace=None, new_data=None):
    """Write a new CFB. If `target_sid_to_replace` is given, replace that
    stream's data with `new_data` before writing."""
    if target_sid_to_replace is not None:
        entries[target_sid_to_replace].data = new_data

    sids = sorted(entries.keys())
    n_entries = max(sids) + 1 if sids else 0
    while n_entries % DIR_ENTRIES_PER_SECTOR != 0:
        n_entries += 1

    mini_sids = []
    big_sids = []
    for sid in sids:
        de = entries[sid]
        if sid == 0:
            continue  # root handled specially
        if de.etype != 2 or de.data is None or len(de.data) == 0:
            continue
        if len(de.data) < MINISTREAM_CUTOFF:
            mini_sids.append(sid)
        else:
            big_sids.append(sid)

    # Pack mini-streams into a single big container (root's stream).
    minifat = []
    ministream = bytearray()
    for sid in mini_sids:
        de = entries[sid]
        data = de.data
        n = (len(data) + MINISECTORSIZE - 1) // MINISECTORSIZE
        first_mini = len(minifat)
        for k in range(n):
            if k == n - 1:
                minifat.append(ENDOFCHAIN)
            else:
                minifat.append(len(minifat) + 1)
            chunk = data[k * MINISECTORSIZE : (k + 1) * MINISECTORSIZE]
            ministream.extend(chunk)
            if len(chunk) < MINISECTORSIZE:
                ministream.extend(b"\x00" * (MINISECTORSIZE - len(chunk)))
        de.start_sect = first_mini
        de.size = len(data)

    ministream_size = len(ministream)
    if ministream_size % SECTORSIZE != 0:
        ministream.extend(b"\x00" * (SECTORSIZE - (ministream_size % SECTORSIZE)))

    while len(minifat) % MINIFAT_ENTRIES_PER_SECTOR != 0:
        minifat.append(FREESECT)

    big_payload_chunks = []
    SID_MINISTREAM = "ministream"
    big_chain_info = []

    def add_big(label, data):
        if not data:
            return
        n = (len(data) + SECTORSIZE - 1) // SECTORSIZE
        first = len(big_payload_chunks)
        for k in range(n):
            chunk = data[k * SECTORSIZE : (k + 1) * SECTORSIZE]
            if len(chunk) < SECTORSIZE:
                chunk = chunk + b"\x00" * (SECTORSIZE - len(chunk))
            big_payload_chunks.append(chunk)
        big_chain_info.append((label, first, n))

    if ministream_size > 0:
        add_big(SID_MINISTREAM, bytes(ministream))
    for sid in big_sids:
        add_big(sid, entries[sid].data)

    payload_sector_count = len(big_payload_chunks)
    minifat_sector_count = len(minifat) // MINIFAT_ENTRIES_PER_SECTOR
    dir_sector_count = n_entries // DIR_ENTRIES_PER_SECTOR

    fat_sector_count = 1
    while True:
        total_managed = (
            payload_sector_count + minifat_sector_count
            + dir_sector_count + fat_sector_count
        )
        difat_sector_count = 0
        if fat_sector_count > HEADER_DIFAT_COUNT:
            extra = fat_sector_count - HEADER_DIFAT_COUNT
            difat_sector_count = (extra + DIFAT_ENTRIES_PER_SECTOR - 1) // DIFAT_ENTRIES_PER_SECTOR
        total_managed += difat_sector_count
        needed = (total_managed + FAT_ENTRIES_PER_SECTOR - 1) // FAT_ENTRIES_PER_SECTOR
        if needed <= fat_sector_count:
            break
        fat_sector_count = needed

    cursor = 0
    payload_first = cursor
    cursor += payload_sector_count
    minifat_first = cursor
    cursor += minifat_sector_count
    dir_first = cursor
    cursor += dir_sector_count
    fat_first = cursor
    cursor += fat_sector_count
    difat_first = cursor
    cursor += difat_sector_count

    fat = [FREESECT] * (fat_sector_count * FAT_ENTRIES_PER_SECTOR)

    def write_chain(first_idx, n, label):
        for k in range(n):
            if k == n - 1:
                fat[first_idx + k] = ENDOFCHAIN
            else:
                fat[first_idx + k] = first_idx + k + 1

    ministream_first_sector = ENDOFCHAIN
    for label, first, count in big_chain_info:
        write_chain(payload_first + first, count, label)
        if label == SID_MINISTREAM:
            ministream_first_sector = payload_first + first
        else:
            entries[label].start_sect = payload_first + first
            entries[label].size = len(entries[label].data)

    if minifat_sector_count > 0:
        write_chain(minifat_first, minifat_sector_count, "minifat")
        first_minifat_sector = minifat_first
    else:
        first_minifat_sector = ENDOFCHAIN

    write_chain(dir_first, dir_sector_count, "directory")
    first_dir_sector = dir_first

    for k in range(fat_sector_count):
        fat[fat_first + k] = FATSECT
    for k in range(difat_sector_count):
        fat[difat_first + k] = DIFSECT

    root = entries[0]
    root.start_sect = ministream_first_sector
    root.size = ministream_size

    header_difat = [FREESECT] * HEADER_DIFAT_COUNT
    fat_sector_indices = [fat_first + k for k in range(fat_sector_count)]
    for k in range(min(fat_sector_count, HEADER_DIFAT_COUNT)):
        header_difat[k] = fat_sector_indices[k]

    difat_sectors = []
    if fat_sector_count > HEADER_DIFAT_COUNT:
        extras = fat_sector_indices[HEADER_DIFAT_COUNT:]
        for i in range(difat_sector_count):
            buf = bytearray(b"\xff" * SECTORSIZE)
            slice_ = extras[i * DIFAT_ENTRIES_PER_SECTOR : (i + 1) * DIFAT_ENTRIES_PER_SECTOR]
            for j, idx in enumerate(slice_):
                struct.pack_into("<I", buf, j * 4, idx)
            next_difat = ENDOFCHAIN if i == difat_sector_count - 1 else difat_first + i + 1
            struct.pack_into("<I", buf, SECTORSIZE - 4, next_difat)
            difat_sectors.append(bytes(buf))

    header = bytearray(SECTORSIZE)
    header[0:8] = CFB_SIGNATURE
    struct.pack_into("<H", header, 24, 0x003E)
    struct.pack_into("<H", header, 26, 3)
    struct.pack_into("<H", header, 28, 0xFFFE)
    struct.pack_into("<H", header, 30, 9)
    struct.pack_into("<H", header, 32, 6)
    struct.pack_into("<I", header, 40, dir_sector_count)
    struct.pack_into("<I", header, 44, fat_sector_count)
    struct.pack_into("<I", header, 48, first_dir_sector)
    struct.pack_into("<I", header, 52, 0)
    struct.pack_into("<I", header, 56, MINISTREAM_CUTOFF)
    struct.pack_into("<I", header, 60, first_minifat_sector)
    struct.pack_into("<I", header, 64, minifat_sector_count)
    if difat_sector_count > 0:
        struct.pack_into("<I", header, 68, difat_first)
    else:
        struct.pack_into("<I", header, 68, ENDOFCHAIN)
    struct.pack_into("<I", header, 72, difat_sector_count)
    for k in range(HEADER_DIFAT_COUNT):
        struct.pack_into("<I", header, 76 + k * 4, header_difat[k])

    dir_bytes = bytearray(dir_sector_count * SECTORSIZE)
    for sid in range(n_entries):
        de = entries.get(sid)
        off = sid * 128
        if de is None:
            struct.pack_into("<I", dir_bytes, off + 68, NOSTREAM)
            struct.pack_into("<I", dir_bytes, off + 72, NOSTREAM)
            struct.pack_into("<I", dir_bytes, off + 76, NOSTREAM)
            continue
        name_utf16 = de.name.encode("utf-16-le") + b"\x00\x00"
        if len(name_utf16) > 64:
            name_utf16 = name_utf16[:62] + b"\x00\x00"
        dir_bytes[off : off + len(name_utf16)] = name_utf16
        struct.pack_into("<H", dir_bytes, off + 64, len(name_utf16))
        dir_bytes[off + 66] = de.etype
        dir_bytes[off + 67] = de.color
        struct.pack_into("<I", dir_bytes, off + 68, de.left)
        struct.pack_into("<I", dir_bytes, off + 72, de.right)
        struct.pack_into("<I", dir_bytes, off + 76, de.child)
        dir_bytes[off + 80 : off + 96] = de.clsid
        dir_bytes[off + 96 : off + 100] = de.state_bits
        dir_bytes[off + 100 : off + 108] = de.ctime
        dir_bytes[off + 108 : off + 116] = de.mtime
        struct.pack_into("<I", dir_bytes, off + 116, de.start_sect)
        struct.pack_into("<Q", dir_bytes, off + 120, de.size)

    minifat_bytes = bytearray(minifat_sector_count * SECTORSIZE)
    for i, v in enumerate(minifat):
        struct.pack_into("<I", minifat_bytes, i * 4, v)

    fat_bytes = bytearray(fat_sector_count * SECTORSIZE)
    for i, v in enumerate(fat):
        struct.pack_into("<I", fat_bytes, i * 4, v)

    out = bytearray()
    out.extend(header)
    for chunk in big_payload_chunks:
        out.extend(chunk)
    out.extend(minifat_bytes)
    out.extend(dir_bytes)
    out.extend(fat_bytes)
    for d in difat_sectors:
        out.extend(d)

    with open(out_path, "wb") as f:
        f.write(out)


if __name__ == "__main__":
    import sys
    if len(sys.argv) == 3:
        entries = load(sys.argv[1])
        dump(entries, sys.argv[2])
        print(f"round-tripped {sys.argv[1]} -> {sys.argv[2]}")
