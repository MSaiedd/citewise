"""Exercise the real browser UI with disposable identities and temporary state.

Install .[browser], then run `playwright install chromium` before this script.
Screenshots are generated from synthetic data; no real credential is embedded.
"""

import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
from playwright.sync_api import expect, sync_playwright


def main():
    root = Path(__file__).resolve().parents[1]
    shots = root / "docs/screenshots"
    shots.mkdir(parents=True, exist_ok=True)
    customer, operator = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    tokens = {
        customer: {"tenant": "demo", "user": "alice"},
        operator: {"tenant": "demo", "user": "staff", "role": "operator"},
    }
    with tempfile.TemporaryDirectory() as temporary:
        env = os.environ.copy()
        env.update(API_TOKENS=json.dumps(tokens), DB_PATH=str(Path(temporary) / "app.db"))
        # Local smoke runs must not inherit a developer's external provider settings.
        env.update(ANSWER_BACKEND="extractive", AGENT_BACKEND="baseline")
        for key in ("MODEL_ID", "ADAPTER_PATH", "EMBEDDING_MODEL"):
            env.pop(key, None)

        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        address = f"http://127.0.0.1:{port}"
        command = [
            sys.executable,
            "-m",
            "uvicorn",
            "citewise.api:create_app",
            "--factory",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ]
        with (Path(temporary) / "server.log").open("w") as log:
            process = subprocess.Popen(command, cwd=root, env=env, stdout=log, stderr=log)
            try:
                ready = False
                for _ in range(100):
                    try:
                        if httpx.get(address + "/health", timeout=1).status_code == 200:
                            ready = True
                            break
                    except httpx.HTTPError:
                        pass
                    if process.poll() is not None:
                        raise RuntimeError(
                            "Server failed: " + (Path(temporary) / "server.log").read_text()
                        )
                    time.sleep(0.1)
                if not ready:
                    raise RuntimeError("Server startup timed out")
                errors = []
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch()
                    page = browser.new_page(
                        viewport={"width": 1280, "height": 1050}, device_scale_factor=1
                    )
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.goto(address)
                    page.locator("#token").fill(customer)
                    page.get_by_role("button", name="Add or replace document").click()
                    expect(page.locator("#ingest-result")).to_contain_text("Saved")
                    page.get_by_role("button", name="Find evidence").click()
                    expect(page.locator("#answer")).to_contain_text("five business days")
                    expect(page.locator("#answer")).to_contain_text("Returns policy")
                    page.screenshot(path=str(shots / "desktop.png"), full_page=True)
                    page.set_viewport_size({"width": 390, "height": 844})
                    assert page.evaluate(
                        "document.documentElement.scrollWidth <= window.innerWidth"
                    ), "Mobile horizontal overflow"
                    page.screenshot(path=str(shots / "mobile.png"), full_page=True)
                    assert not errors, errors
                    browser.close()
                print("PASS: desktop flow, mobile layout, no uncaught browser errors")
            finally:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


if __name__ == "__main__":
    main()
