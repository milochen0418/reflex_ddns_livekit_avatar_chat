import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def main() -> int:
    base_url = os.getenv("BASE_URL", "http://127.0.0.1:3000").rstrip("/")
    output_dir = Path(os.getenv("OUTPUT_DIR", "testcases/smoke_home/output"))
    output_dir.mkdir(parents=True, exist_ok=True)

    headless = env_bool("HEADLESS", True)
    timeout_ms = int(os.getenv("PW_TIMEOUT_MS", "30000"))

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless, slow_mo=int(os.getenv("PW_SLOWMO_MS", "0"))
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 800}, ignore_https_errors=True
        )
        page = context.new_page()
        page.set_default_timeout(timeout_ms)

        try:
            page.goto(base_url + "/", wait_until="domcontentloaded")
            page.get_by_role("heading", name="Avatar Rooms").wait_for()
            page.get_by_role("button", name="Join Room").wait_for()

            # First start may download livekit-server; allow up to 2 minutes.
            page.locator('#server-status[data-phase="running"]').wait_for(timeout=120_000)
            print("server status:", page.locator("#server-status").inner_text())

            # The vendored SDK, avatar renderer, face tracker and bridge must be loaded (no CDN).
            page.wait_for_function(
                "() => !!window.LivekitClient && !!window.AvatarFace && !!window.FaceTracker && !!window.livekitClient"
            )
            # The style picker shows the four avatars, drawn (and blinking) by the bridge.
            page.wait_for_function(
                "() => [...document.querySelectorAll('canvas[data-avatar-preview]')]"
                ".filter((c) => c.width > 0).length === 4"
            )

            # The face tracker (MediaPipe) is served by the app itself.
            for name, kind in (
                ("vision_bundle.js", "javascript"),
                ("vision_wasm_internal.js", "javascript"),
                ("vision_wasm_internal.wasm", "wasm"),
                ("face_landmarker.task", ""),
            ):
                asset = context.request.get(f"{base_url}/mediapipe/{name}")
                content_type = asset.headers.get("content-type", "")
                print(f"GET /mediapipe/{name} ->", asset.status, content_type, len(asset.body()), "bytes")
                if asset.status != 200 or kind not in content_type:
                    raise AssertionError(f"/mediapipe/{name}: {asset.status} {content_type}")

            # The backend relays /rtc to livekit-server: without a token it must
            # answer with LiveKit's own 401, not a 404 (no route) or 502 (no server).
            backend_url = os.getenv("BACKEND_URL") or base_url.replace(":3000", ":8000")
            resp = context.request.get(backend_url + "/rtc/validate")
            print("GET /rtc/validate ->", resp.status, resp.text()[:120])
            if resp.status != 401:
                raise AssertionError(f"/rtc/validate relay returned {resp.status}")

            page.screenshot(path=str(output_dir / "smoke.png"), full_page=True)
            return 0
        except Exception:
            try:
                page.screenshot(path=str(output_dir / "failure.png"), full_page=True)
            except Exception:
                pass
            raise
        finally:
            context.close()
            browser.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise
    except Exception as exc:
        print(f"smoke_home failed: {exc}", file=sys.stderr)
        raise
