# Custom Firmware

This firmware is based on the official M5Stack UIFlow MicroPython firmware:

```text
https://github.com/m5stack/uiflow-micropython
```

The custom build was made from the M5Stack Dial board configuration:

```text
m5stack/boards/M5STACK_Dial/sdkconfig.board
```

## Custom MBEDTLS Setting

The only custom MBEDTLS setting added for this project is:

```text
CONFIG_MBEDTLS_DYNAMIC_BUFFER=y
```

## Why This Is Needed

The M5Stack Dial has limited heap available for UIFlow2, LVGL, Wi-Fi, icons, and
HTTPS requests. TLS handshakes can require a large contiguous memory block for
mbedTLS buffers and X.509 certificate parsing.

Enabling `CONFIG_MBEDTLS_DYNAMIC_BUFFER=y` lets mbedTLS allocate TLS input and
output buffers only when needed, instead of keeping the full buffers allocated
for the whole TLS session. This reduces heap pressure and helps HTTPS requests
run more reliably on the device.

The resulting firmware image is stored in this repository as:

```text
firmware/firmwareM5DialCustom.bin
```
