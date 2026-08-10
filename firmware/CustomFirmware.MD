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
