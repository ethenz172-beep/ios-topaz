#!/usr/bin/env python3
"""Wrap a shim Image in the Mi 6's stock Android boot v0 container.

The kernel field of the stock image contains a gzip-compressed arm64 Image
followed by Qualcomm FDT blobs. Preserve that board data, the stock v0 header,
ramdisk and second stage, replacing only the compressed Image. Use with
`fastboot boot`; this tool does not write to a phone.
"""
from __future__ import annotations

import gzip
import hashlib
import struct
import sys
import zlib
from pathlib import Path

PAGE = 4096
FDT_MAGIC = b"\xd0\x0d\xfe\xed"
ARM64_IMAGE_MAGIC = b"ARM\x64"


def align(n: int, unit: int = PAGE) -> int:
    return (n + unit - 1) // unit * unit


def build(stock_path: Path, kernel_path: Path, out_path: Path) -> None:
    stock = stock_path.read_bytes()
    if stock[:8] != b"ANDROID!":
        raise ValueError("template is not an Android boot image")
    kernel_size, _, ramdisk_size, _, second_size, _, _, page, header_version = struct.unpack_from(
        "<9I", stock, 8
    )
    if header_version != 0 or page != PAGE:
        raise ValueError(f"expected boot header v0/page {PAGE}, got v{header_version}/page {page}")

    kernel_start = page
    kernel_end = kernel_start + kernel_size
    stock_kernel = stock[kernel_start:kernel_end]
    dec = zlib.decompressobj(16 + zlib.MAX_WBITS)
    dec.decompress(stock_kernel)
    dtbs = dec.unused_data
    if FDT_MAGIC not in dtbs:
        raise ValueError("template kernel has no appended Qualcomm FDT data")

    ramdisk_start = page + align(kernel_size)
    ramdisk = stock[ramdisk_start:ramdisk_start + ramdisk_size]
    second_start = ramdisk_start + align(ramdisk_size)
    second = stock[second_start:second_start + second_size]
    if len(ramdisk) != ramdisk_size or len(second) != second_size:
        raise ValueError("template is truncated")

    image = kernel_path.read_bytes()
    if len(image) < 64 or image[56:60] != ARM64_IMAGE_MAGIC:
        raise ValueError("kernel input is not an arm64 Linux Image (missing ARM64 magic)")
    new_kernel = gzip.compress(image, compresslevel=9, mtime=0) + dtbs
    header = bytearray(stock[:page])
    struct.pack_into("<I", header, 8, len(new_kernel))
    digest = hashlib.sha1()
    for part in (new_kernel, ramdisk, second):
        digest.update(part)
        digest.update(struct.pack("<I", len(part)))
    header[576:608] = digest.digest().ljust(32, b"\0")

    pad = lambda part: part + b"\0" * (align(len(part)) - len(part))
    out_path.write_bytes(bytes(header) + pad(new_kernel) + pad(ramdisk) + pad(second))
    print(f"{out_path}: boot v0, {out_path.stat().st_size} bytes; shim={len(image)} bytes; preserved Qualcomm FDT={len(dtbs)} bytes")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("usage: pack_sagit_boot.py STOCK_BOOT.img SHIM.Image OUT_BOOT.img")
    build(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
