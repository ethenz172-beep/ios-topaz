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

## Remaining blockers

- The screen stopped updating after early IOKit/CPU initialization, but no
  panic banner or fault details were captured. The XNU console does not provide
  Android ADB, and this payload has no serial/KDP capture configured. Add
  later-stage breadcrumbs or capture a debugger trace before attributing the
  stop to the last printed line.
- The payload contains only the XNU kernel and ADT; no iOS root filesystem or
  RAM disk is included. Reaching the normal BSD root-device wait is therefore
  a later expected milestone, not a usable iOS boot.
- The initial boot args disable unported Topaz touch, key/USB, battery,
  CPU-frequency, backlight, GPU and modem paths. The Sagit boot-arg also disables
  Topaz's hard-coded MDP scanout registers. The MSM8998 display update path is
  still unimplemented; framebuffer writes may not appear on the command-mode panel.
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
  or write an iOS root to userdata in this stage.
