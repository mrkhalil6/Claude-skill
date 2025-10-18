# RFP Analyzer with Claude Skills API

This script uses Claude's Skills API to analyze RFP (Request for Proposal) documents, automatically highlighting questions/requirements in blue and marking answer locations in green.

## Setup

1. **Install dependencies** (already done):
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   pip install -r requirements.txt
   ```

2. **Set your API key**:
   - Open the `.env` file (already created)
   - Replace `your_api_key_here` with your actual Anthropic API key
   ```
   ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxx
   ```

3. **Add RFP files**:
   - Place your `.docx` or `.xlsx` files in the `input/` directory
   - The script will process all files in that folder

## Usage

```bash
# Make sure you're in the virtual environment
.\venv\Scripts\Activate.ps1

# Run the script
python rfp_analyzer.py
```

## What it does

1. Scans the `input/` folder for `.docx` and `.xlsx` files
2. Uploads each file to Claude
3. Uses Claude Skills (docx and xlsx) to:
   - Identify all questions and requirements
   - Highlight them in **BLUE**
   - Mark answer locations in **GREEN**
4. Downloads the analyzed files to the `output/` directory

## Output

Analyzed files will be saved in the `output/` directory with the same filename as the input.

## Requirements

- Python 3.7+
- Valid Anthropic API key with access to Skills API
- Beta features enabled: code execution, skills, and files API

