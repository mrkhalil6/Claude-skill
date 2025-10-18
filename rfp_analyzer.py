import os
import logging
from pathlib import Path
import anthropic
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
INPUT_DIR = Path("input")
OUTPUT_DIR = Path("output")
BETA_HEADERS = [
    "code-execution-2025-08-25",
    "skills-2025-10-02",
    "files-api-2025-04-14"
]

def setup_directories():
    """Create input and output directories if they don't exist."""
    try:
        INPUT_DIR.mkdir(exist_ok=True)
        OUTPUT_DIR.mkdir(exist_ok=True)
        logger.info(f"Directories ready: {INPUT_DIR}, {OUTPUT_DIR}")
    except Exception as e:
        logger.exception(f"Failed to create directories: {e}")
        raise

def get_api_key():
    """Get API key from environment variable."""
    try:
        logger.info("Retrieving API key from environment...")
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        logger.info("API key found successfully")
        return api_key
    except Exception as e:
        logger.exception(f"Failed to get API key: {e}")
        raise

def upload_file_to_container(client, file_path):
    """Upload a file to the code execution container."""
    try:
        file_size = os.path.getsize(file_path) / 1024  # KB
        logger.info(f"Uploading file to container: {file_path} ({file_size:.2f} KB)")
        logger.info("Opening file in binary mode...")
        with open(file_path, "rb") as f:
            logger.info("Calling Anthropic Files API upload endpoint...")
            uploaded_file = client.beta.files.upload(
                file=f,
                betas=["files-api-2025-04-14"]
            )
        logger.info(f"✓ File uploaded successfully")
        logger.info(f"  File ID: {uploaded_file.id}")
        logger.info(f"  Filename: {uploaded_file.filename}")
        return uploaded_file
    except Exception as e:
        logger.exception(f"Failed to upload file {file_path}: {e}")
        raise

def analyze_rfp_with_claude(client, uploaded_file, original_filename):
    """Send file to Claude for RFP analysis with Skills."""
    try:
        logger.info("Preparing Claude API request...")
        file_extension = Path(original_filename).suffix.lower()
        
        # Determine which skill to use based on file type
        logger.info(f"Detected file extension: {file_extension}")
        if file_extension == '.docx':
            skill_id = 'docx'
            file_type = "Word document"
        elif file_extension == '.xlsx':
            skill_id = 'xlsx'
            file_type = "Excel spreadsheet"
        else:
            raise ValueError(f"Unsupported file type: {file_extension}")
        
        logger.info(f"File type: {file_type}")
        logger.info(f"Sending request to Claude API with:")
        logger.info(f"  Model: claude-sonnet-4-5-20250929")
        logger.info(f"  Beta headers: {', '.join(BETA_HEADERS)}")
        logger.info(f"  Skills: docx, xlsx")
        logger.info(f"  Tools: code_execution")
        logger.info(f"  Attached file ID: {uploaded_file.id}")
        
        # Create message with beta features
        response = client.beta.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=8192,
            betas=BETA_HEADERS,
            container={
                "skills": [
                    {"type": "anthropic", "skill_id": "docx", "version": "latest"},
                    {"type": "anthropic", "skill_id": "xlsx", "version": "latest"}
                ]
            },
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"""I have uploaded an RFP (Request for Proposal) {file_type}.

Please:
1. Load and read the {file_type} file
2. Identify ALL requirements, questions, or items that need responses in this RFP
3. Highlight ALL questions and requirements with BLUE color/background (RGB: 68, 114, 196 or #4472C4)
4. For EACH question/requirement, detect exactly where the answer should go and:
   - Insert the placeholder text "<Answer_HERE>" at that exact location
   - Highlight the placeholder with GREEN color/background (RGB: 112, 173, 71 or #70AD47)
5. Preserve the original document structure and formatting
6. Save the modified document as: highlighted_{original_filename}
7. Make sure the file is exposed/returned so it can be downloaded

IMPORTANT: Every question/requirement you highlight in BLUE must have a corresponding "<Answer_HERE>" placeholder in GREEN where the response should be written.

Use the docx and xlsx skills available to you to properly format and save the file."""
                    },
                    {
                        "type": "container_upload",
                        "file_id": uploaded_file.id
                    }
                ]
            }],
            tools=[{
                "type": "code_execution_20250825",
                "name": "code_execution"
            }]
        )
        
        logger.info("Claude analysis completed")
        
        # Log the full response for debugging
        logger.info("="*60)
        logger.info("RESPONSE DETAILS:")
        logger.info(f"Response ID: {response.id}")
        logger.info(f"Model: {response.model}")
        logger.info(f"Stop Reason: {response.stop_reason}")
        logger.info(f"Content blocks: {len(response.content)}")
        
        for i, content_block in enumerate(response.content):
            logger.info(f"\nContent Block {i}:")
            logger.info(f"  Type: {content_block.type}")
            logger.info(f"  Content: {content_block}")
        
        logger.info("="*60)
        
        return response
    except Exception as e:
        logger.exception(f"Failed to analyze RFP with Claude: {e}")
        raise

def extract_file_ids(response):
    """Extract file IDs from Claude's response."""
    try:
        logger.info("Extracting file IDs from Claude response...")
        logger.info(f"Scanning {len(response.content)} content blocks...")
        
        file_ids = []
        for idx, item in enumerate(response.content):
            logger.info(f"  Block {idx}: type={item.type}")
            if item.type == 'bash_code_execution_tool_result':
                logger.info(f"    Found code execution result, inspecting contents...")
                content_item = item.content
                if content_item.type == 'bash_code_execution_result':
                    for file_idx, file in enumerate(content_item.content):
                        if hasattr(file, 'file_id'):
                            logger.info(f"    ✓ Found file {file_idx}: {file.file_id}")
                            file_ids.append(file.file_id)
        
        logger.info(f"✓ Extracted {len(file_ids)} file ID(s) from response")
        if file_ids:
            for fid in file_ids:
                logger.info(f"  - {fid}")
        return file_ids
    except Exception as e:
        logger.exception(f"Failed to extract file IDs: {e}")
        raise

def download_analyzed_file(client, file_id, output_path, original_filename):
    """Download the analyzed file from Claude."""
    try:
        logger.info(f"Downloading file: {file_id}")
        
        # Get file metadata
        logger.info("Step 1/3: Retrieving file metadata...")
        file_metadata = client.beta.files.retrieve_metadata(
            file_id=file_id,
            betas=["files-api-2025-04-14"]
        )
        logger.info(f"  Metadata retrieved - Filename: {file_metadata.filename}")
        
        # Download file content
        logger.info("Step 2/3: Downloading file content...")
        file_content = client.beta.files.download(
            file_id=file_id,
            betas=["files-api-2025-04-14"]
        )
        logger.info("  File content downloaded successfully")
        
        # Use the metadata filename or construct from original
        if file_metadata.filename:
            output_filename = file_metadata.filename
        else:
            # Construct the expected highlighted filename
            output_filename = f"highlighted_{original_filename}"
        
        logger.info(f"  Output filename: {output_filename}")
        
        # Save to output directory
        logger.info("Step 3/3: Saving file to disk...")
        output_file = output_path / output_filename
        file_content.write_to_file(str(output_file))
        
        saved_size = os.path.getsize(output_file) / 1024  # KB
        logger.info(f"✓ File saved successfully: {output_file} ({saved_size:.2f} KB)")
        return output_file
    except Exception as e:
        logger.exception(f"Failed to download file {file_id}: {e}")
        raise

def process_file(client, file_path):
    """Process a single RFP file."""
    try:
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing: {file_path.name}")
        logger.info(f"{'='*60}")
        
        # Upload file to container
        logger.info("[STEP 1/4] Uploading file to Claude container...")
        uploaded_file = upload_file_to_container(client, file_path)
        
        # Analyze with Claude
        logger.info("[STEP 2/4] Sending to Claude for analysis...")
        response = analyze_rfp_with_claude(client, uploaded_file, file_path.name)
        
        # Extract file IDs from response
        logger.info("[STEP 3/4] Extracting generated file IDs...")
        file_ids = extract_file_ids(response)
        
        if not file_ids:
            logger.warning(f"⚠ No output files generated for {file_path.name}")
            return
        
        # Download all generated files
        logger.info(f"[STEP 4/4] Downloading {len(file_ids)} generated file(s)...")
        for idx, file_id in enumerate(file_ids, 1):
            logger.info(f"Downloading file {idx}/{len(file_ids)}...")
            download_analyzed_file(client, file_id, OUTPUT_DIR, file_path.name)
        
        logger.info(f"✓ Successfully processed: {file_path.name}")
        logger.info(f"{'='*60}\n")
        
    except Exception as e:
        logger.exception(f"✗ Failed to process file {file_path.name}: {e}")

def main():
    """Main function to process all RFP files."""
    try:
        logger.info("="*60)
        logger.info("RFP ANALYZER STARTING")
        logger.info("="*60)
        
        # Setup
        logger.info("\n[INITIALIZATION] Setting up environment...")
        setup_directories()
        api_key = get_api_key()
        
        logger.info("Creating Anthropic API client...")
        client = anthropic.Anthropic(api_key=api_key)
        logger.info("✓ API client created successfully")
        
        # Find all docx and xlsx files
        logger.info(f"\n[FILE DISCOVERY] Scanning '{INPUT_DIR}' directory...")
        input_files = list(INPUT_DIR.glob("*.docx")) + list(INPUT_DIR.glob("*.xlsx"))
        
        if not input_files:
            logger.warning(f"⚠ No .docx or .xlsx files found in {INPUT_DIR}")
            logger.info(f"Please add RFP files to the '{INPUT_DIR}' directory")
            return
        
        logger.info(f"✓ Found {len(input_files)} file(s) to process:")
        for idx, file in enumerate(input_files, 1):
            file_size = os.path.getsize(file) / 1024
            logger.info(f"  {idx}. {file.name} ({file_size:.2f} KB)")
        
        # Process each file
        logger.info(f"\n[PROCESSING] Starting batch processing...")
        for idx, file_path in enumerate(input_files, 1):
            logger.info(f"\nFile {idx}/{len(input_files)}")
            process_file(client, file_path)
        
        logger.info("\n" + "="*60)
        logger.info("✓ ALL FILES PROCESSED SUCCESSFULLY!")
        logger.info(f"Check the '{OUTPUT_DIR}' directory for analyzed files")
        logger.info("="*60)
        
    except Exception as e:
        logger.exception(f"✗ Application error: {e}")
        raise

if __name__ == "__main__":
    main()

