# TableStory

TableStory is a responsive recipe discovery app for Hearth & Harvest. Find a recipe by dish, ingredient or dietary need, read its ingredients and steps, and save it to My Cookbook, on a phone or on a TV with a remote.

It is built with Python, Flask, HTML, CSS and vanilla JavaScript. It needs no database, API key or network access once dependencies are installed.

## Install

```sh
python -m pip install -r demo-app/requirements.txt
```

## Run

```sh
python demo-app/app.py
```

- Mobile: <http://127.0.0.1:5000/>
- TV: <http://127.0.0.1:5000/?mode=tv>

TV mode is also selected by recognised TV user agents. Use the arrow keys, Enter, and Escape or Backspace to navigate it.

## Test

```sh
pytest -q demo-app/tests
node --test demo-app/static/tests/*.test.js
git diff --check
```

The Python tests include a release scan (`demo-app/tests/test_release_scan.py`) that checks shipped files, symbols, rendered pages and API payloads for leftover terms from the old app, confirms the old routes return 404, and confirms no dependencies were added.
