# Custom Firmware

This firmware is based on the official M5Stack UIFlow MicroPython firmware:

```text
https://github.com/m5stack/uiflow-micropython
```

The custom build was made from the M5Stack Dial board configuration:

```text
m5stack/boards/M5STACK_Dial/sdkconfig.board
```

## Custom MBEDTLS Settings

The custom MBEDTLS settings added for this project are:

```text
CONFIG_MBEDTLS_DYNAMIC_BUFFER=y
CONFIG_MBEDTLS_DYNAMIC_FREE_CONFIG_DATA=y
CONFIG_MBEDTLS_DYNAMIC_FREE_CA_CERT=y
CONFIG_MBEDTLS_ASYMMETRIC_CONTENT_LEN=y
CONFIG_MBEDTLS_SSL_IN_CONTENT_LEN=16384
CONFIG_MBEDTLS_SSL_OUT_CONTENT_LEN=2048
CONFIG_MBEDTLS_SSL_KEEP_PEER_CERTIFICATE=n
```

## Why This Is Needed

The M5Stack Dial has limited heap available for UIFlow2, LVGL, Wi-Fi, icons, and
HTTPS requests. TLS handshakes can require a large contiguous memory block for
mbedTLS buffers and X.509 certificate parsing.

Enabling `CONFIG_MBEDTLS_DYNAMIC_BUFFER=y` lets mbedTLS allocate TLS input and
output buffers only when needed, instead of keeping the full buffers allocated
for the whole TLS session. The dynamic-free options reduce certificate/config
retention after the TLS handshake, and the asymmetric content length limits keep
the outgoing TLS buffer smaller than the incoming buffer.

The full generated firmware image is intentionally not stored in this
repository. The repack base archive contains the native build artifacts needed
to rebuild the final firmware asset:

```text
firmware/UHS-m5dial-repack-base.zip
```

## Runtime bytecode packaging

The repack workflow builds `mpy-cross` from the UIFlow MicroPython `2.4.2` tag
and compiles runtime Python modules to `.mpy` before creating both the complete
LittleFS image and the update diff. `main.py` remains the source entrypoint so
the UIFlow startup path is unchanged. `config.py.example` remains available on
the device, while the private `config.py` is never packaged.

The first `.mpy` release includes every compiled module in its migration diff
for devices that were installed from `.py` sources. On later updates, installing
`foo.mpy` removes `foo.py` at the same path when it exists; the updater never
scans the filesystem to remove unrelated Python files.

## DRAM Budget and TLS Failures

### Measured Problem

On a device running the launcher with Wi-Fi connected, every HTTPS request
fails in `ssl.wrap_socket` with `OSError: [Errno 12] ENOMEM`, whatever the
target host. `esp32.idf_heap_info(esp32.HEAP_DATA)` reported four regions,
as `(total, free, largest_free_block, min_free_ever)`:

```text
(248136, 4, 0, 4)          # 100% allocated
(22308, 4, 0, 4)           # 100% allocated
(32768, 5108, 4608, 3128)
(8068, 7688, 7680, 7688)
```

Only 12804 bytes were free out of 311280, and the largest contiguous block was
7680 bytes because it sits in a region that is only 8068 bytes long. That block
cannot grow, whatever the application frees.

| Consumer | Bytes | Share |
| --- | --- | --- |
| MicroPython GC heap | 189568 | 61% |
| Wi-Fi, lwIP, LVGL, IDF | ~108900 | 35% |
| Free for mbedTLS | 12804 | 4% |

`gc.mem_alloc()` / `gc.mem_free()` reported 138304 / 51264: MicroPython holds
51264 free bytes inside its own heap that `malloc()` can never reach. The port
sets `MICROPY_GC_SPLIT_HEAP_AUTO`, so that heap grows on demand and does not
give the memory back. This is why the application-level memory work
(`memory_cleanup()`, `release_all()`, JSON spooling, module eviction) has no
effect on this failure: it frees the Python heap, and the Python heap is not
the exhausted resource.

Wi-Fi is what empties the only region large enough for TLS. Across the boot
trace, `c_largest` goes from 31744 before `wlan.connect()`, to 11264 right
after, to 7680 once the link is up.

The handshake peak is roughly 20-25 KB held simultaneously: SSL context and
config, entropy and DRBG, ECDHE handshake parameters, an RX buffer sized on the
incoming record, the X.509 chain being parsed, and the TX buffer. The largest
single allocation is around 7-8 KB, which is why 7680 free bytes fail right at
the edge. The `api.brewfather.app` chain is 4 certificates, 6892 bytes of DER
in a single TLS record.

### DRAM Recovery Settings

Applied to `m5stack/boards/M5STACK_Dial/sdkconfig.board`. DRAM figures marked
*measured* come from per-archive static allocation in `micropython.map`; the
others are derived from buffer counts and confirmed by the post-build heap
dump.

```text
CONFIG_BT_ENABLED=n
CONFIG_ESP_WIFI_STATIC_RX_BUFFER_NUM=4
CONFIG_ESP_WIFI_DYNAMIC_RX_BUFFER_NUM=12
CONFIG_ESP_WIFI_DYNAMIC_TX_BUFFER_NUM=12
CONFIG_ESP_WIFI_MGMT_SBUF_NUM=8
CONFIG_ESP_WIFI_AMPDU_RX_ENABLED=n
CONFIG_LWIP_TCP_SND_BUF_DEFAULT=2880
CONFIG_LWIP_TCP_WND_DEFAULT=2880
CONFIG_LWIP_TCP_QUEUE_OOSEQ=n
CONFIG_ESP32S3_DATA_CACHE_16KB=y
```

| Setting | Expected gain | Basis |
| --- | --- | --- |
| `ESP32S3_DATA_CACHE_16KB` | 16384 | Cache is carved out of internal SRAM |
| `ESP_WIFI_STATIC_RX_BUFFER_NUM` 10 to 4 | 9600 | 6 buffers of ~1600 B at `esp_wifi_init()` |
| `BT_ENABLED=n` | 7283 DRAM | Measured: `libbt.a` 5808, `libbtdm_app.a` 1173, `libcoexist.a` 302 |
| `BT_ENABLED=n`, IRAM share | 0-17746 | Measured in the map, but returning to the data heap is unverified |
| `LWIP_TCP_WND`/`SND_BUF` 5760 to 2880 | ~5700 | Per active socket, during the handshake |
| `ESP_WIFI_AMPDU_RX_ENABLED=n` | 4000-8000 | RX reorder buffers, estimated |

Disabling `CONFIG_BT_ENABLED` also requires `MICROPY_PY_BLUETOOTH (0)` in the
board's `mpconfigboard.h`: `micropython/ports/esp32/mpconfigport.h` defaults it
to 1 behind a bare `#ifndef`, and the board header is included first.

Two further changes are required, both found the hard way when the link and
then the compile failed.

`build-M5STACK_Dial/genhdr` must be deleted after the config change.
`moduledefs.h` is a generated header that ninja does not re-derive from
`mpconfigboard.h`, so a stale copy keeps `mp_module_bluetooth` in the module
table and the link fails on an undefined reference.

The BLE Python libraries must be dropped from the frozen manifest. The default
`MICROPY_FROZEN_MANIFEST` is `m5stack/boards/manifest.py`, which pulls in
`m5stack/libs/manifest.py`, which freezes `bleuart` and `m5ble`. Their bytecode
references QSTRs such as `MP_QSTR_gap_scan` and `MP_QSTR_gatts_notify` that only
exist when `MICROPY_PY_BLUETOOTH` is on, so `frozen_content.c` fails to compile.
Comment out the `bleuart` and `m5ble` includes in `m5stack/libs/manifest.py`.

Nothing on the boot path imports `bluetooth`, and the `unit` package resolves
its drivers lazily through an `_attrs` table, none of which touch BLE.

### Build Procedure

From `m5stack/`, the build is `make BOARD=M5STACK_Dial pack_all`. Three stale
artefacts must be cleared first, or the change silently fails to apply:

```sh
rm -f  build-M5STACK_Dial/sdkconfig   # generated config wins over the defaults
rm -rf build-M5STACK_Dial/genhdr      # stale moduledefs.h keeps the BT entry
rm -f  build-M5STACK_Dial/frozen_content.c
```

The first is the one that bites hardest: once ESP-IDF has written
`build-M5STACK_Dial/sdkconfig`, values already in it take precedence over
`sdkconfig.board`, so editing the board file alone changes nothing and the build
still succeeds. Check the effective values in the generated `sdkconfig` after
building, never in `sdkconfig.board`.

Source the ESP-IDF that lives **inside the uiflow tree**
(`uiflow-micropython/esp-idf/export.sh`), not a separate system-wide checkout.
Incremental builds survive the wrong `IDF_PATH` because the absolute paths are
baked into the cmake cache, but any full reconfigure then fails with "The source
... does not match the source ... used to generate cache" on the bootloader
subproject.

Note also that `make` returning through a wrapper can mask a failed build.
Verify `build-M5STACK_Dial/micropython.elf` exists and is freshly dated rather
than trusting an exit code.

### Measured Result

With `MICROPY_PY_BLUETOOTH (0)` alone, before any sdkconfig value took effect:

| | Baseline | With BLE dropped | Delta |
| --- | --- | --- | --- |
| Static D/IRAM used | 150747 | 125411 | **-25336** |
| `.data` | 20928 | 20016 | -912 |
| `.bss` | 34312 | 28152 | -6160 |
| D/IRAM `.text` | 95507 | 77243 | -18264 |

Nothing references NimBLE any more, so the linker drops `libbt.a` and
`libbtdm_app.a` entirely. That recovers more than the 7283 bytes of static DRAM
measured in the map, because the BT controller code was also occupying IRAM in
the unified ESP32-S3 SRAM pool.

With the full sdkconfig set applied on a clean build dir:

| | Baseline | Final | Delta |
| --- | --- | --- | --- |
| Static D/IRAM used | 150747 | 124983 | -25764 |
| Static D/IRAM remaining | 191013 | 216777 | **+25764** |
| BT archive members linked | many | 0 | |

`CONFIG_BT_ENABLED=n` adds only 428 bytes over `MICROPY_PY_BLUETOOTH (0)` alone,
because the linker had already dropped every BT member once nothing referenced
them. Keep both: the sdkconfig value is what stops the component being built at
all, and it is the honest expression of intent.

This static figure **understates** the runtime gain. It is computed against a
fixed DRAM region in the linker script, so it does not show the data-cache
carve-out, and it cannot show the Wi-Fi buffer pools, which are heap
allocations made at `esp_wifi_init()`. The remaining recovery -- 9600 bytes of
static RX buffers, the AMPDU reorder buffers, the management short buffers, the
halved TCP window, and possibly 16384 bytes from the data cache -- appears only
at runtime. Confirm it with the acceptance test below, not with the size
report.


Deliberately left alone: `CONFIG_LWIP_MAX_SOCKETS` and
`CONFIG_LWIP_TCPIP_RECVMBOX_SIZE` save very little and risk starving the UIFlow
cloud connection; `CONFIG_LWIP_IPV6=n` is worth 2-4 KB but the mDNS component
in this build may not compile without it. Reducing the data cache slows flash
reads, so it is the first candidate to revert if the margin allows.

### Acceptance Test

Boot to the launcher, wait for Wi-Fi, interrupt with Ctrl+C, then at the REPL:

```python
import gc, esp32, requests2
gc.collect()
print(esp32.idf_heap_info(esp32.HEAP_DATA))
r = requests2.get("https://api.github.com/rate_limit")
print("gh", r.status_code)
r.close()
```

The target is 35-40 KB free with a largest block of at least 12 KB, against
12804 and 7680 before the change.

Disable the runtime watchdog before running this test. If `WATCHDOG_TIMEOUT_MS`
is set in `config.py`, `machine.WDT` is armed and cannot be disarmed; once the
main loop stops feeding it the board resets, and three such resets trigger the
lockout screen.

### Shipping Through CI

`.github/workflows/repack-firmware.yml` does not build the ESP-IDF firmware. It
unpacks `firmware/UHS-m5dial-repack-base.zip` and repacks the native artifacts
with a freshly built user filesystem, so shipping a new firmware means
refreshing that archive.

Three of its six native artifacts changed with this build; the other three are
byte-identical, which confirms no local state leaked into the image:

| Artifact | Status |
| --- | --- |
| `artifacts/micropython.bin` | replaced, 5891120 to 5686256 bytes |
| `artifacts/bootloader/bootloader.bin` | replaced, same size, rebuilt |
| `artifacts/sdkconfig` | replaced, carries the new values |
| `artifacts/partition_table/partition-table.bin` | unchanged |
| `artifacts/nvs.bin` | unchanged |
| `artifacts/fs-system.bin` | unchanged |

`firmware/uiflow-dram-recovery.patch` holds the full delta against upstream
uiflow-micropython 2.4.2 for the three source files, the pre-existing mbedTLS
settings included. Apply it with `git apply` in an
`uiflow-micropython` checkout at tag `2.4.2`, then follow the build procedure
above.

### Status

Validated on hardware: the device boots to the launcher and the Brewfather API
calls that previously failed with `ENOMEM` now succeed. Flash only the app,
bootloader and partition table (`@flash_args`); writing the full 8 MB image at
0x0 also rewrites the filesystem and NVS, which destroys `config.py` and the
stored Wi-Fi credentials.
