# AXS Scraper

A small asynchronous scraper for AXS event pages built with Python, Playwright and CloakBrowser.

The scraper opens a configured event page, works with proxy sessions, waits for the final ticket page state and saves a screenshot after a successful load.

## Browser Fingerprint and Proxy Quality

CloakBrowser handles the browser fingerprint automatically, including the user agent, platform-related values, WebGL, Canvas, AudioContext and other browser characteristics. Because of that, the project does not add custom fingerprint spoofing on top of CloakBrowser.

In practice, scraper stability depends heavily on proxy quality. More trusted proxies usually provide a noticeably higher success rate. During testing, mobile proxies reached approximately 75-85% successful runs, while lower-quality or heavily used proxies were blocked much more often.

## Features

- CloakBrowser-based browser sessions
- HTTP, HTTPS and SOCKS5 proxy support
- Proxy validation before use
- Proxy list hot reload without restarting the application
- Separate browser storage state for proxy sessions
- Detection of Cloudflare and AXS restriction pages
- Success and failed screenshots
- File and console logging
- Docker support
- Configuration through YAML and environment variables

## Project Structure

```text
.
├── config/
│   ├── data/
│   │   └── proxies.txt
│   └── settings.yaml
├── core/
│   ├── browser.py
│   ├── exceptions.py
│   └── scraper.py
├── models/
├── utils/
├── application.py
├── dependencies.py
├── run.py
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## Configuration

Main settings are stored in:

```text
config/settings.yaml
```

Example:

```yaml
application_settings:
  event_page: "https://shop.axs.com/..."
  use_proxy: true
  proxy_check_concurrency: 20
  proxy_file: "config/data/proxies.txt"

cloak_browser_settings:
  headless: true
  version: "152.x.x.x"
  license_key: ""
```

Environment variables can override values from `settings.yaml`.

Supported environment variables:

```text
AXS_EVENT_PAGE
AXS_USE_PROXY
AXS_PROXY_CHECK_CONCURRENCY
AXS_PROXY_FILE
CLOAKBROWSER_HEADLESS
CLOAKBROWSER_VERSION
CLOAKBROWSER_LICENSE_KEY
```

## Proxies

Add proxies to:

```text
config/data/proxies.txt
```

Supported formats:

```text
http://username:password@host:port
https://username:password@host:port
socks5://username:password@host:port
```

Proxies are checked before being added to the runtime pool.

The proxy file is monitored while the application is running, so proxies can be added or removed without restarting the scraper.

## Local Run

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it.

Windows:

```powershell
.venv\Scripts\Activate.ps1
```

Linux/macOS:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the scraper:

```bash
python run.py
```

## Docker

The project can be started completely inside Docker.

Build and run:

```bash
docker compose up --build
```

Run in the background:

```bash
docker compose up -d --build
```

View logs:

```bash
docker compose logs -f
```

Stop the container:

```bash
docker compose stop
```

Remove the container:

```bash
docker compose down
```

The following directories are mounted from the host:

```text
screenshots/
logs/
storage/
```

The proxy file is mounted separately:

```text
config/data/proxies.txt
```

## Output

Successful screenshots:

```text
screenshots/success/
```

Failed screenshots:

```text
screenshots/failed/
```

Application logs:

```text
logs/
```

Browser session state:

```text
storage/
```

Storage state is reused for matching proxy sessions and contains cookies and local storage data.

