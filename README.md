## Quick Start

### 1. Requirements

- Python 3.10 or newer

### 2. Download and Install

Go to the [Releases page](https://github.com/qoobatov/ultratrace_refactoring/releases)
and download the latest `ultratrace-vX.X.X.zip` file. Extract it to a
folder of your choice.

### Install

Open a terminal in the extracted folder

```bash
python -m venv venv
source venv/bin/activate      # Linux/macOS
# or: venv\Scripts\activate   # Windows
pip install .
```

### 3. Prepare your data

Place your study folder (containing `.dicom` or `.ult` files, audio,
and a `.TextGrid` file) somewhere on your computer — for example, a
folder called `my_study`.

### 4. Run

From inside your study folder:

```bash
ultratrace web
```

If you don't specify a folder, a window will open asking you to select
your study data directory. You can also pass the path directly:

```bash
ultratrace web /path/to/your/study
```

You should see:

Starting server
Open http://localhost:3000 in your browser

Your browser will open automatically at `http://localhost:3000` with
UltraTrace ready to use, loaded with the data from the current folder.

**Optional flags:**

```bash
ultratrace web /path/to/other_study   # use a different data folder
ultratrace web -p 8080                # run on a different port
ultratrace web -n                     # don't open a browser automatically
```

To stop the server, press `Ctrl+C` in the terminal.

---

## Development Setup

This section is for developers working on UltraTrace itself. The
frontend and backend live in separate repositories and are run
independently for hot-reloading during development.

### Backend

```bash
python -m venv venv
source venv/bin/activate      # Linux/macOS
# or: venv\Scripts\activate   # Windows

pip install -r requirements.txt
```

By default the backend looks for study data in `data/sample_study`.
To use a different folder, set an environment variable:

```bash
export ULTRA_TRACE_DATA=/full/path/to/folder
# on Windows: set ULTRA_TRACE_DATA=C:\path\to\folder
```

Run the backend:

```bash
uvicorn app.main:app --reload
```

This starts the API server at `http://127.0.0.1:8000`.

### Frontend

In the separate `ultratrace-frontend` repository:

```bash
npm install
npm run dev
```

This starts the frontend at `http://localhost:5173`, which talks to
the backend at `http://127.0.0.1:8000` automatically.

### Building a release

To package a new version for the Quick Start install above, the
frontend needs to be built and copied into the backend repository:

```bash
# in ultratrace-frontend
npm run build

# copy the build output into the backend repo
cp -r dist /path/to/ultratrace-backend/frontend_dist
```

The backend will then serve this build automatically when run via
`ultratrace web` or `uvicorn app.main:app`.
