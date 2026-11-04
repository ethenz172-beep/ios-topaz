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
- The saved live FDT confirms MDSS at `0x0c900000` and DSI0 at `0x0c994000`
  (controller window `0x400`, PHY at `0x0c994400`). It identifies the active
  panel as JDI FHD R63452, 1080x1920, four lanes, DSI command mode, software DMA
  trigger, and no MDP trigger. The active panel node carries its own on/off and
  DCS setup command tables; use those data rather than guessing a sequence.
- The live FDT specifies `bl_ctrl_wled`, so the panel backlight is PMIC WLED
  controlled. Sailfish's one-byte DCS `0x51` brightness helper is not the
  Sagit backlight path and remains disabled. Upstream MSM8998 calls its display
  engine DPU; Pixel 1's MSM8996 MDP5 kickoff/pipe register writes cannot serve
  as Sagit's scanout implementation.
- The early XNU CPU tree exposes only Gold cores, starting at MPIDR `0x100`.

Values came from the connected Mi 6's live FDT and are not a generic MSM8998
reference configuration.

## Hosted build path

The `xnu.yml` workflow has a Sagit job on the `sagit-port` branch. Run
41844858240 completed successfully: both the XNU build and `sagit-bringup`
jobs passed. The artifact contains the Sagit ADT, payload and shim Image, but
no handset boot image or device dump. Artifact SHA256 values were verified
before packaging.

After downloading the `sagit-bringup` artifact to Windows, create a temporary
boot v0 image locally from the saved stock boot image:

```powershell
python tools\pack_sagit_boot.py C:\path\to\backed-up\boot.img `
  C:\path\to\sagit-shim.Image C:\path\to\sagit-fastboot-boot.img
```

Use `fastboot boot sagit-fastboot-boot.img` only. Do not use `fastboot flash`.
The generated image was accepted by `fastboot boot` on a connected Mi 6
(`product: sagit`); after 60 seconds the device was no longer visible to either
ADB or fastboot. This confirms the bootloader handed off the image, but does
not confirm that XNU reached a usable prompt or that the display is working.
The user's screen photo subsequently confirmed visible XNU kernel output:
the boot CPU came alive with SGI1 verified, `1/1 CPUs initialized`, and kernel
subsystems continued initializing. No panic banner is visible. The last
visible lines are in `m_processor_register` for CPU 0. The user confirmed the
screen then stopped updating. CPU bring-up itself completed. `pset 0` is the
scheduler's processor-set ID in that diagnostic, not an error code; the last
printed line alone does not prove the kernel stopped inside that function. The
exact wait or fault still needs a serial/KDP trace or additional boot logging.
The `gPanicBase is still not initialized` message is expected for this build:
patch 0004 defines `PLATFORM_PANIC_LOG_DISABLED`, so persistent panic-log
storage is disabled. The phone has since returned to Android 8.0 and is again
visible to ADB (`product:sagit`).

## Local build path

Generate the Sagit Apple Device Tree:

```sh
python3 tools/mkadt.py shim/out/sagit.adt --sagit
```

Build and wrap the shim using the stock Android v0 boot image as a template:

```sh
SAGIT=1 SAGIT_BOOT_TEMPLATE=/path/to/backed-up/boot.img ./shim/build.sh [payload.bin]
```

`tools/pack_sagit_boot.py` preserves the stock header, ramdisk and appended
Qualcomm DTBs while replacing the kernel Image. The hosted Sagit shim was
compiled and packaged; the first `fastboot boot` handoff succeeded, but no
ADB/fastboot re-enumeration was seen within 60 seconds.

## iOS 16.7.16 source and root image

- The user-provided iPhone X IPSW is `P:\iPhone10,3,iPhone10,6_16.7.16_20H392_Restore.ipsw`, SHA256 `ece1194f7e233e9109c5790a8d23a4564a10a254e15ec5b09978a343265568fb`. Its manifest is build `20H392`, board `D22AP`. This is an extraction source only; it must not be restored to the Mi 6.
- APFS members `OS.dmg` (4,730,814,044 bytes), `SystemOS.dmg` (2,743,074,816 bytes), and `AppOS.dmg` (10,485,760 bytes) were extracted to `P:\ios16-20H392\`.
- Experimental combined root image: `P:\ios16-20H392\iosroot-hfsplus.img`, 16 GiB, SHA256 `8fa7fd01429606c7d2c90886c5fd1e5581095f8da345dbe0c988c2ef69fc5f6b`. It includes the OS volume, both cryptexes, shared dyld cache links and the keybag/logd setup from `tools/mkiosroot.sh`.
- Windows had WSL 2 but no Ubuntu distribution. Ubuntu 24.04 was imported into `P:\WSL\ios-sweet-rootfs`; APFS-FUSE was built from `sgan81/apfs-fuse` and `fstool` 0.4.35's x86_64 static release was SHA256-verified against the GitHub release API (`0ac6836e68876be814b93fd6d9cca26733b85ac989ab31621376c0af55a8a809`). WSL's stock kernel has neither `HFSPLUS_FS` nor `HFS_FS`, so the normal `mkiosroot.sh` mount path could not run. `fstool` directly wrote the HFS+ image instead. `fsck.hfsplus -f -n` reports the result OK after `fsck.hfsplus -f -y` normalized names; `fstool` can list `/sbin/launchd`, the shared cache and `/private/var/keybags/systembag.kb`.
- Limitation: this `fstool` build emits plain case-insensitive HFS+, while `mkiosroot.sh` intends case-sensitive HFS+. A scan found no NFD+casefold name collisions. The image was later written to `userdata` as 35 fastboot sparse parts with user approval, but it has not been mounted by the Sagit XNU payload; Android user data was overwritten. Boot, bootloader and recovery partitions were not written by that operation.

## Remaining blockers

- The screen stopped updating after early IOKit/CPU initialization, but no
  panic banner or fault details were captured. The XNU console does not provide
  Android ADB, and this payload has no serial/KDP capture configured. Add
  later-stage breadcrumbs or capture a debugger trace before attributing the
  stop to the last printed line.
- The current payload still contains only the XNU kernel and ADT; the separate
  experimental HFS+ root image above has not been integrated. Reaching the
  normal BSD root-device wait is therefore a later expected milestone, not a
  usable iOS boot.
- The initial boot args disable unported Topaz touch, key/USB, battery,
  CPU-frequency, backlight, GPU and modem paths. The Sagit boot-arg also disables
  Topaz's hard-coded MDP scanout registers. The MSM8998 display update path is
  still unimplemented; framebuffer writes may not appear on the command-mode panel.
- Local diagnostic patch edits now initialize the early XNU screen logger from
  `boot_args.Video`, align the bootstrap/final mappings to that framebuffer's
  32 MiB block, and remove the pre-MMU fixed `0x9c000000` write. This should
  restore the stage markers on Sagit's `0x9d400000` 1080x1920 splash area; the
  patch series has not yet been applied against XNU or built by Actions.
- The command-mode panel's update path has not been tested from the shim/XNU;
  a readable framebuffer address alone does not prove display updates work.
- Pixel 1's `sweet_fbcon_kick` writes MSM8996 MDP5 VIG0/CTL0 registers and
  uses its own DSI command helper. Reuse only the general frame-completion and
  packet-queueing ideas after validating MSM8998 DSI register behavior; do not
  transplant its MDP5 pipe, flush, mixer, or brightness assumptions.
- Sagit's live FDT exposes a software DSI DMA trigger but no MDP trigger for
  the panel. The missing work is the MSM8998-specific command-mode pixel
  transfer path and safe scanout/flush programming; DSI base discovery alone
  does not make framebuffer updates work.
- Topaz-specific XNU drivers and match strings still need review. Leave
  unported touch, USB, Wi-Fi, GPU, battery and frequency drivers disabled.
- Keep using `fastboot boot` during early bring-up. Do not flash boot partitions
  or write another image to userdata in this stage. The experimental HFS+ image is already there; the current kernel payload has no confirmed Sagit UFS/root integration, so it cannot use that volume yet.
