# Dependency cleanup plan

## Keep (required by current code)

| Package | Why keep it | Evidence in code |
|---|---|---|
| `flask` | Web app framework (app factory, routes, request/response). | `app/__init__.py`, `app/routes/main_routes.py` |
| `beautifulsoup4` | HTML parsing for component counting and heuristics. | `engine/analysis/utils/html_parser.py`, `engine/transformation/services/heuristic_evaluator.py` |
| `playwright==1.46.0` | Rendering HTML in headless Chromium for screenshot analysis. | `engine/rendering/services/gui_rendering.py` |
| `Pillow` | Image loading/conversion to RGB before pixel analysis. | `engine/rendering/utils/pixel_frequency.py` |
| `numpy` | Pixel array handling and serialization support. | `engine/rendering/utils/pixel_frequency.py`, `engine/analysis/utils/file_manager.py` |

## Remove (currently unused in repo code)

| Package | Why remove it now | Notes |
|---|---|---|
| `selenium` | No imports/usages found in project Python code. | Keep only if you plan to migrate rendering/automation to Selenium. |
| `chromedriver-autoinstaller` | No imports/usages found in project Python code. | Only needed when Selenium + ChromeDriver are used together. |

## Optional pinning recommendation

- Consider pinning all direct dependencies to exact versions to make builds reproducible (as already done for Playwright).
- Example strategy: pin direct dependencies in `requirements.txt`, then regenerate a lock/frozen file (`pip freeze > requirements.lock.txt`) per environment.

## Minimal requirements proposal

```txt
flask
beautifulsoup4
Pillow
numpy
playwright==1.46.0
```

## Safe validation workflow

1. Create a fresh virtual environment.
2. Install the minimal requirements.
3. Install Chromium for Playwright:
   - `python -m playwright install chromium`
4. Run the app and execute a full upload → analysis → results flow.
5. If everything passes, remove the unused packages from the main `requirements.txt`.

## Can this run automatically or is it manual?

Both options are possible:

- **Manual**: follow each validation step one by one (good for debugging).
- **Automatic**: run the command block below in a fresh environment.

### Automatic validation (Linux/macOS)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
python app/app.py
```

### Automatic validation (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium
python app\app.py
```

> Note: this starts the app automatically, but functional verification of upload → analyze → results is still a user/browser action unless you add an automated test suite.

