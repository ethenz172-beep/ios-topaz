# Xiaomi Mi 6 (`sagit`) port status

This is an early experimental port branch based on the ARMv8.0 Snapdragon work
in ios-topaz. It does not contain a bootable iOS image yet.

## Board facts used by the initial configuration

- SoC: Qualcomm MSM8998; CPU MPIDRs `0..3` (Silver) and `0x100..0x103` (Gold).
- XNU RAM window: `0x100000000` + `0x7e4c0000`. The live FDT's fixed and
  dynamically allocated reserved pools are confined below 4 GiB.
- GICv3: distributor `0x17a00000`, redistributor `0x17b00000`, stride `0x20000`.
- UFS host: `0x1da4000`; active framebuffer reservation `0x9d400000`;
  panel `1080x1920`, command mode.
- The early XNU CPU tree exposes only Gold cores, starting at MPIDR `0x100`.

Values came from the connected Mi 6's live FDT and are not a generic MSM8998
reference configuration.

## Current local build path

Generate the Sagit Apple Device Tree:

```sh
python3 tools/mkadt.py shim/out/sagit.adt --sagit
```

Build and wrap the shim using the stock Android v0 boot image as a template:

```sh
SAGIT=1 SAGIT_BOOT_TEMPLATE=/path/to/backed-up/boot.img ./shim/build.sh [payload.bin]
```

`tools/pack_sagit_boot.py` preserves the stock header, ramdisk and appended
Qualcomm DTBs while replacing the kernel Image. The output is for `fastboot
boot` only. The script was round-trip checked with a synthetic arm64 Image;
the Sagit shim itself has not been compiled or boot-tested.

## Remaining blockers

- The current Windows host has no AArch64 compiler. A hosted build job is still
  needed for both the shim and XNU.
- The command-mode panel's update path has not been tested from the shim/XNU;
  a readable framebuffer address alone does not prove display updates work.
- Topaz-specific XNU drivers and match strings still need review. Leave
  unported touch, USB, Wi-Fi, GPU, battery and frequency drivers disabled.
- Keep using `fastboot boot` during early bring-up. Do not flash boot partitions
  or write an iOS root to userdata in this stage.
