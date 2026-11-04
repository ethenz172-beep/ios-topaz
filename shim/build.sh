#!/bin/bash
# Build the shim; Topaz uses boot v4, while Sagit reuses its stock boot v0
# header, ramdisk and appended Qualcomm DTBs.
set -euo pipefail
cd "$(dirname "$0")"
CC=${AARCH64_CC:-aarch64-linux-gnu-gcc}
OBJCOPY=${AARCH64_OBJCOPY:-aarch64-linux-gnu-objcopy}
READELF=${AARCH64_READELF:-aarch64-linux-gnu-readelf}
NM=${AARCH64_NM:-aarch64-linux-gnu-nm}
SAGIT=${SAGIT:-0}
CFLAGS="-O2 -ffreestanding -nostdlib -fno-pic -mgeneral-regs-only -mstrict-align -fno-stack-protector -Wall -Wextra"
if [ "$SAGIT" = 1 ]; then
	CFLAGS="$CFLAGS -DSAGIT"
fi
mkdir -p out
for f in start.S shim.c console.c mmu.c fdt.c loader.c ufs.c; do
	$CC $CFLAGS -c $f -o out/${f%.*}.o
done
# The image runs wherever ABL puts it with no relocation pass: only the
# header's image_size (start.o, linked at 0) may be an absolute address.
abs=$($READELF -r out/shim.o out/console.o out/mmu.o out/fdt.o out/loader.o out/ufs.o | grep -c ABS64 || true)
[ "$abs" = 0 ] || { echo "error: $abs absolute relocations in C objects" >&2; exit 1; }
$CC $CFLAGS -static -T shim.ld -Wl,--build-id=none -Wl,--no-warn-rwx-segments -Wl,-N \
	out/start.o out/shim.o out/console.o out/mmu.o out/fdt.o out/loader.o out/ufs.o -o out/shim.elf
$OBJCOPY -O binary out/shim.elf out/Image
# ABL copies the file; pad to image_size so .bss/stacks exist as zeroed bytes.
size=$((16#$($NM out/shim.elf | awk '$3=="_end"{print $1}')))
truncate -s "$size" out/Image
if [ "$SAGIT" = 1 ]; then
	if [ -n "${1:-}" ]; then
		# Payload follows _end, where shim/loader.c looks for it.
		truncate -s $(( (size + 0xfff) & ~0xfff )) out/Image
		cat "$1" >> out/Image
		python3 -c 'import os,struct,sys; f=open(sys.argv[1],"r+b"); f.seek(16); f.write(struct.pack("<Q", os.path.getsize(sys.argv[1])))' out/Image
	fi
	# Package locally with the owner's stock template, or leave a raw Image for CI.
	if [ -n "${SAGIT_BOOT_TEMPLATE:-}" ]; then
		python3 ../tools/pack_sagit_boot.py "$SAGIT_BOOT_TEMPLATE" out/Image out/shim-boot.img
		ls -l out/Image out/shim-boot.img
	else
		cp out/Image out/sagit-shim.Image
		ls -l out/Image out/sagit-shim.Image
	fi
	${HOST_CC:-gcc} -O1 -Wall -o out/host_test console.c host_test.c && ./out/host_test
	exit 0
fi
# Ramdisk: an xnu payload (tools/mkpayload.py) if given as $1, else an empty
# newc cpio (ABL dislikes a zero-size ramdisk on some builds) -> diagnostics.
if [ -n "${1:-}" ]; then
	# topaz ABL drops the v4 boot ramdisk: append the payload to the Image at
	# the first 4K boundary after _end (loader.c) and grow image_size.
	truncate -s $(( (size + 0xfff) & ~0xfff )) out/Image
	cat "$1" >> out/Image
	python3 -c 'import os,struct,sys; f=open(sys.argv[1],"r+b"); f.seek(16); f.write(struct.pack("<Q", os.path.getsize(sys.argv[1])))' out/Image
	(cd out && rm -rf rd && mkdir rd && cd rd && find . | cpio -o -H newc --quiet | gzip -9 > ../ramdisk.bin)
else
	(cd out && rm -rf rd && mkdir rd && cd rd && find . | cpio -o -H newc --quiet | gzip -9 > ../ramdisk.bin)
fi
${MKBOOTIMG:-python3 /home/makr/work/topaz/mkbootimg_src/mkbootimg.py} --header_version 4 --kernel out/Image --ramdisk out/ramdisk.bin \
	--os_version 13.0.0 --os_patch_level 2025-01 \
	--cmdline "console=null" -o out/shim-boot.img
# Host render of the console layout.
gcc -O1 -Wall -o out/host_test console.c host_test.c && ./out/host_test
ls -l out/Image out/shim-boot.img
