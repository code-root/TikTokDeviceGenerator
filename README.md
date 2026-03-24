# TikTok Device Generator

Desktop GUI (**Tkinter**) that generates device-registration payloads via **Java / unidbg**, POSTs them to TikTok’s **device register** endpoint, and saves results as **JSON** with **batch mode**, **threading**, and optional **proxy** support.

**Documentation:** **English** (this file) · **[Arabic — README.ar.md](README.ar.md)**

> **Notice:** Use this tool only in compliance with applicable laws and service terms. This document describes technical behavior only.

---

## Table of contents

1. [What it does](#what-it-does)
2. [Requirements](#requirements)
3. [Installation](#installation)
4. [Run](#run)
5. [Project layout](#project-layout)
6. [User interface](#user-interface)
7. [Output files & JSON](#output-files--json)
8. [Proxy](#proxy)
9. [Java & native libraries](#java--native-libraries)
10. [Troubleshooting](#troubleshooting)
11. [Credits](#credits)
12. [Maintainer, company & contact](#maintainer-company--contact)
13. [Support this project](#support-this-project)

---

## What it does

1. Builds random inputs (e.g. `openudid`, timestamps, MAC-like pattern) and passes them to **Java** through **`Libs/unidbg.jar`**, loading natives from **`Libs/prebuilt/<platform>/`**.
2. Parses the **binary payload** from unidbg stdout (`hex=…` block).
3. Sends **POST** to `https://log-va.tiktokv.com/service/2/device_register/` with fixed headers and `content-type: application/octet-stream;tt-data=a`.
4. On successful JSON, stores **`device_id`**, **`install_id`** (and string variants when present) plus metadata.
5. In **batch** mode, runs many devices in parallel with **`ThreadPoolExecutor`**; **Stop** cancels remaining work (in-flight tasks may still finish).

---

## Requirements

| Component | Notes |
|-----------|--------|
| **Python** | Modern syntax (e.g. `str \| None`). **Python 3.10+** recommended. |
| **Packages** | See `requirements.txt` — notably **`requests[socks]`** for SOCKS proxies. |
| **Java** | JVM able to run **`Libs/unidbg.jar`**. On **64-bit Windows**, use **64-bit Java** to match **`Libs/prebuilt/win64/`**. |
| **Repo files** | **`Libs/unidbg.jar`** and **`Libs/prebuilt/<platform>/`** (e.g. `win64`, `linux64`, `osx64`). |

---

## Installation

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

Install a **JDK/JRE** and verify `java -version`. If only **32-bit** Java is installed on **64-bit Windows** while the app uses **win64** natives, unidbg will fail — see [Java & native libraries](#java--native-libraries).

---

## Run

```bash
python DeviceGenerator.py
```

There is no separate CLI; all options are in the GUI. A prebuilt **`.exe`** may be available from **Releases** (same `Libs` / Java expectations).

---

## Project layout

```
TikTokDeviceGenerator-main/
├── DeviceGenerator.py      # GUI + batch worker + HTTP
├── requirements.txt
├── README.md               # This file (English)
├── README.ar.md            # Arabic documentation
├── assets/                 # Support / deposit QR images
├── Libs/
│   ├── unidbg.jar
│   └── prebuilt/           # win64, linux64, osx64, ...
├── Device/                 # devices_001.json, ...
└── generated_devices/      # _batch_summary_*.json
```

Code constants:

- **`DEVICES_PER_JSON_FILE = 50`** — records per file under `Device/`.
- **`DEVICE_REGISTER_URL`** — register endpoint URL.

---

## User interface

**Header** — app title and short subtitle.

**Action bar**

- **Start** — validates `unidbg.jar`, `Libs/prebuilt/<platform>`, counts, threads, and proxy URL (if any).
- **Stop** — signals cancel; pending futures are cancelled; progress reflects completed work.
- **Open output folder** — opens the folder path currently shown in **Output folder** (e.g. `os.startfile` on Windows).

**Batch options**

- **Number of devices** — 1–9999.
- **Threads** — 1–64, capped by device count.
- **Output folder** — path shown in the field and used only for **Open output folder**.  
  **Important:** `DeviceGenerator.py` always writes device chunks to **`<project>/Device/`** and batch summaries to **`<project>/generated_devices/`**, regardless of this field. Change it to open another folder for convenience (e.g. after you point it at `generated_devices`).
- **Proxy URL (optional)** — applied to all `device_register` requests in the batch.

**Last device (preview)** — read-only **OpenUDID**, **Device ID**, **IID** with **Copy** buttons; updates on each **successful** registration in the current batch.

**Progress** — indeterminate while preparing, then determinate by completed/total; status line combines count/percent and a short message.

**Log** — per device: URL, headers, hex preview of body, response or errors. **`request_log`** is **stripped** before writing each record to **`Device/devices_*.json`** to keep files smaller; the UI still shows full logs during the run.

---

## Output files & JSON

**`Device/`**

- Files `devices_001.json`, …; part numbers continue from the highest existing `devices_*.json`.
- Each file: `saved_at`, `part`, `devices_per_file`, `count`, and **`devices`**: `[{ "batch_index": n, "record": { ... } }, …]`.
- **`record`** includes fields like `status`, `input`, `network`, ids, `register_response`, etc., usually **without** `request_log`.

**`generated_devices/`**

- Each batch run creates **`_batch_summary_YYYYMMDD_HHMMSS.json`** with `requested_devices`, `threads`, `success`, `failed`, `completed_tasks`, `cancelled`, paths, chunk size, and **`network`** (including **`proxy_url_masked`** when a proxy is used).

**Default “Output folder” field**

- Initialized to **`<project>/generated_devices`** via `default_output_dir()` so it matches where summaries are written; you may edit the field for which folder **Open output folder** opens.

---

## Proxy

Supported schemes: **`http`**, **`https`**, **`socks5`**, **`socks5h`**.

```text
http://127.0.0.1:8080
http://user:password@host:port
socks5h://127.0.0.1:1080
```

Install **`requests[socks]`** for SOCKS. Exported JSON uses **`proxy_url_masked`** under **`network`** when credentials are present.

---

## Java & native libraries

Approximate invocation from `Libs/`:

```text
java -jar -Djna.library.path="<prebuilt>" -Djava.library.path="<prebuilt>" unidbg.jar "<message>"
```

`<prebuilt>` is `Libs/prebuilt/<getsystem()>` (e.g. `win64` on 64-bit Windows).

**`get_java_exe()`** tries **`JAVA_HOME`**, a common Windows path, then **`java`** on `PATH`. On 64-bit Windows it prefers a JVM that reports **64-Bit** in `java -version` output.

---

## Troubleshooting

| Symptom | Likely cause |
|---------|----------------|
| `Missing unidbg.jar` | File missing at `Libs/unidbg.jar`. |
| `Missing native libraries` | Wrong or missing `Libs/prebuilt/<platform>`. |
| unidbg fails / no `hex=…` | Wrong Java arch, bad cwd, or unexpected JVM output (check Log / stderr in failure payload). |
| HTTP / JSON errors | Network, block, bad proxy, or non-JSON response. |
| SOCKS fails | Missing **`requests[socks]`** or unsupported URL. |
| Tk / button errors | Use official Python with Tk; for PyInstaller builds, bundle Tcl/Tk correctly. |

---

## Credits

- Original work attributed to **[xSaleh](https://github.com/xSaleh)** — thank you.
- Branding / contact in the app footer is defined in `DeviceGenerator.py` (e.g. Storage TE).

---

## Maintainer, company & contact

| | |
|---|---|
| **Developer** | Mostafa Al-Bagouri |
| **Company** | **[Storage TE](http://storage-te.com/)** |
| **WhatsApp** | [+20 100 199 5914](https://wa.me/201001995914) |

---

## Support this project

If this tool is useful to you, optional support helps maintain and improve it. Pick whatever works best for you.

| Channel | How to support |
|--------|----------------|
| **Buy Me a Coffee** | Quick card payment — [buymeacoffee.com/loukious](https://buymeacoffee.com/loukious) |
| **PayPal** | [paypal.me/sofaapi](https://paypal.me/sofaapi) |
| **Binance Pay / UID** | **1138751298** — send from the Binance app (Pay / internal transfer when available). |
| **Binance — deposit (web)** | [Deposit crypto (Binance)](https://www.binance.com/en/my/wallet/account/main/deposit/crypto) — sign in, pick the asset, then select **BSC (BEP20)**. |
| **BSC address (copy)** | `0x94c5005229784d9b7df4e7a7a0c3b25a08fd57bc` |

> **Network:** Use **BSC (BEP-20)** only. This address is for **USDT (BEP-20)** and **BTC on BSC** (Binance-Peg / in-app “BTC” on BSC), matching the Binance deposit screens below. **Do not** send **native Bitcoin (on-chain BTC)**, **ERC-20**, or **NFTs** to this address.

### Deposit QR codes (scan in Binance or any BSC wallet)

| USDT · BSC | BTC · BSC |
|------------|-----------|
| ![USDT deposit QR — BSC](assets/deposit-usdt-bsc.png) | ![BTC on BSC deposit QR](assets/deposit-btc-bsc.png) |

<p align="center">
  <a href="https://buymeacoffee.com/loukious" title="Buy Me a Coffee">
    <img src="https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png" alt="Buy Me a Coffee" width="180">
  </a>
</p>
