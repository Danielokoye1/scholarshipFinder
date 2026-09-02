"""Verify that guarded browser phases can launch the installed Chrome safely."""

from playwright.sync_api import Error, sync_playwright


def main() -> None:
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="chrome", headless=True)
            browser.close()
    except Error as error:
        raise SystemExit(
            "Guarded browser features require Google Chrome in /Applications. "
            "Install or update Chrome, then run npm run browser:check again."
        ) from error
    print("Browser safety check passed (isolated Chrome context).")


if __name__ == "__main__":
    main()
