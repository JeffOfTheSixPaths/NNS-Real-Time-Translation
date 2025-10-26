# NNS Real-Time Translation — Build & Local Dev

This README documents the simple build process for the static front-end in this folder.

Build commands

- Build using the Python helper (cross-platform):

```bash
python build.py
```

- Build by copying an entire source directory into `dist` (example):

```bash
python build.py path/to/site_dir
```

- If you prefer npm scripts (convenience wrappers):

```cmd
npm run build          # runs python build.py
npm run build:from-src # runs python build.py NNS-Real-Time-Translation
npm run clean          # removes dist/
npm run serve          # serves dist/ at http://localhost:8000
```

Notes

- The build script will look for `index.html` in the repository root, any `*.html` file, or a common static folder (`public`, `build`, `site`, or `NNS-Real-Time-Translation`).
- If `dist/` already contains HTML and no source is found, the script treats the build as already complete.
- Replace the placeholder `dist/index.html` with your real site output to serve it locally or with Cloudflare Pages.
