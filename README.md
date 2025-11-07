# Projects Selection

Filtering and validation of **relevant repositories** collected during the previous stage, **Projects Discovery**.
This step identifies and keeps only repositories that actually use **Cucumber / Behavior-Driven Development (BDD)** and contain valid, testable scenarios.

---

## Installation

Clone this repository and create a Python virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

Install the required dependencies:

```bash
pip install -r requirements.txt
```

---

## Usage

Run the main filtering script:

```bash
python3 -B main.py --input ../dataset/projects_discovery.json --repos-dir ../repositories --output-dir ./output --skip-clone

# or

make
```

### Parameters

| Parameter      | Description                                                                                                                                                                                                                                                                             |
| -------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `--input`      | Path to the **dataset generated in Stage 1 (Projects Discovery)**. Example: `../dataset/projects_discovery`. |
| `--repos-dir`  | Directory where repositories will be cloned or where they are already stored locally.                                                                                                                                                                                                   |
| `--output-dir` | Output directory where the filtered dataset (valid repositories only) will be saved.                                                                                                                                                                                                    |
| `--skip-clone` | Use this flag **only if the repositories have already been cloned locally** on the machine where you are running the script. Otherwise, **omit this parameter** to allow automatic cloning.                                                                                             |

---

## Output

The output directory (`./output`) will contain:

* The final dataset  `projects_selection.json`.
* Execution logs and metadata about the filtering process.

---