#!/usr/bin/env python3
"""Probe EvanMiya's public Shiny Player Ratings table/download.

This script intentionally drives the visible public UI. EvanMiya is an R Shiny
app, so the player-rating rows are not present in the initial HTML.
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", default="2025-26")
    parser.add_argument("--conf", default="All")
    parser.add_argument("--out-dir", default="data/cache/evanmiya")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--try-download", action="store_true")
    parser.add_argument("--system-chrome", action="store_true")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"player_ratings_{slug(args.year)}_{slug(args.conf)}.csv"
    screenshot_path = out_dir / f"player_ratings_{slug(args.year)}_{slug(args.conf)}.png"
    html_path = out_dir / f"player_ratings_{slug(args.year)}_{slug(args.conf)}.html"

    with sync_playwright() as p:
        launch_kwargs = {
            "headless": not args.headed,
            "args": ["--disable-gpu", "--no-first-run"],
        }
        if args.system_chrome:
            launch_kwargs["executable_path"] = CHROME
        browser = p.chromium.launch(**launch_kwargs)
        context = browser.new_context(accept_downloads=True, viewport={"width": 1500, "height": 1000})
        page = context.new_page()

        console_messages: list[str] = []
        page.on("console", lambda msg: console_messages.append(f"{msg.type}: {msg.text}"))

        page.goto("https://evanmiya.com/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_selector("#tab-player_ratings", timeout=60000)
        page.click("#tab-player_ratings")
        page.wait_for_selector("#player_ratings_page-player_data", timeout=60000)

        page.evaluate(
            """({conf, year}) => {
                function setSelect(id, value) {
                    const el = document.querySelector(id);
                    if (!el) throw new Error(`Missing ${id}`);
                    if (el.selectize) {
                        el.selectize.setValue(value, false);
                    } else {
                        el.value = value;
                        el.dispatchEvent(new Event('change', {bubbles: true}));
                    }
                }
                setSelect('#player_ratings_page-conf', conf);
                setSelect('#player_ratings_page-year', year);
            }""",
            {"conf": args.conf, "year": args.year},
        )

        # Give Shiny/reactable time to receive data.
        try:
            page.wait_for_function(
                """() => {
                    const el = document.querySelector('#player_ratings_page-player_data');
                    return el && !el.classList.contains('recalculating');
                }""",
                timeout=45000,
            )
        except PlaywrightTimeoutError:
            pass

        page.screenshot(path=str(screenshot_path), full_page=True)
        html_path.write_text(page.content(), encoding="utf-8")

        if args.try_download:
            try:
                with page.expect_download(timeout=60000) as download_info:
                    page.click("#player_ratings_page-download_player_ratings")
                download = download_info.value
                download.save_as(str(out_path))
                print(f"downloaded={out_path}")
            except Exception as exc:  # noqa: BLE001 - we want the exact probe failure
                print(f"download_failed={exc!r}")

        # The public download button is not reliable in headless mode, but the
        # public reactable can be paged through. Use the largest page size to
        # keep requests gentle.
        page_size = page.locator("#player_ratings_page-player_data .rt-page-size-select")
        if page_size.count() > 0:
            page_size.select_option("1000")
            page.wait_for_timeout(2500)

        columns = [
            "rank",
            "player_name",
            "team",
            "obpr",
            "dbpr",
            "bpr",
            "poss",
            "box_obpr",
            "box_dbpr",
            "box_bpr",
            "adj_team_off_eff",
            "adj_team_def_eff",
            "adj_team_eff_margin",
            "plus_minus",
        ]
        rows: list[list[str]] = []
        seen: set[tuple[str, ...]] = set()
        while True:
            page_rows = page.evaluate(
                """() => {
                    const root = document.querySelector('#player_ratings_page-player_data');
                    if (!root) return [];
                    return Array.from(root.querySelectorAll('.rt-tbody .rt-tr-group .rt-tr'))
                        .map(row => Array.from(row.querySelectorAll('.rt-td'))
                            .map(cell => cell.innerText.trim().replace(/\\s+/g, ' ')))
                        .filter(values => values.length > 0);
                }"""
            )
            for row in page_rows:
                values = tuple(row[: len(columns)])
                if len(values) == len(columns) and values not in seen:
                    seen.add(values)
                    rows.append(list(values))

            page_info = page.locator("#player_ratings_page-player_data .rt-page-info").inner_text(timeout=5000)
            next_button = page.locator("#player_ratings_page-player_data .rt-next-button")
            disabled = next_button.get_attribute("disabled") is not None or next_button.get_attribute("aria-disabled") == "true"
            print(f"scraped_page={page_info} total_rows={len(rows)}", flush=True)
            if disabled:
                break
            next_button.click()
            page.wait_for_timeout(2500)

        with out_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["year", "conference", *columns])
            for row in rows:
                writer.writerow([args.year, args.conf, *row])
        print(f"scraped_csv={out_path}", flush=True)
        print(f"scraped_rows={len(rows)}", flush=True)
        print(f"screenshot={screenshot_path}", flush=True)
        print(f"html={html_path}", flush=True)
        if console_messages:
            print("console_tail:")
            for message in console_messages[-12:]:
                print(message[:500])

        browser.close()

    return 0 if out_path.exists() else 2


if __name__ == "__main__":
    raise SystemExit(main())
