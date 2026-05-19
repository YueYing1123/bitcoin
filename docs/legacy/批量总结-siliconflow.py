import os
import csv
import requests
import time
from docx import Document
import pdfplumber
from tqdm import tqdm

# --- Configuration ---
# !! IMPORTANT: Make sure this path is correct and uses raw string (r"...") or double backslashes (\\) !!
WORK_DIR = r"D:\BaiduSyncdisk\Doctor\FinAI\FDUROP\2025\2025法学院曦源立项材料\2025法学院曦源立项申请书\总目录"
PROMPT_TEMPLATE_FILENAME = "提示词.txt"
OUTPUT_CSV_FILENAME = "summaries.csv"

# Provided list of names/groups
# Each string is an entry; groups are separated by \n within a single string
NAMES_LIST = [
    "赵贤育",
    "韩越",
    "陈希媛",
    "潘婧恬",
    "何雅琳",
    "刘一帜\n赵其姝",
    "张沐妍\n闫佳琪",
    "龚小棠"
]

# --- SiliconFlow API Configuration (as provided by user) ---
API_KEY = r'sk-nhvqrtjcajqjfjbtendrxftpkjoilofamzeqybnlammlzmqs'  # Please replace with your SiliconFlow API密钥
API_URL = r'https://api.siliconflow.cn/v1/chat/completions'

# --- Helper Functions ---

def call_siliconflow_api(prompt, max_retries=5):
    """
    Calls the SiliconFlow API with the given prompt.
    (This function is provided by the user)
    """
    for attempt in range(max_retries):
        try:
            payload = {
                "model": r"",  # 根据实际使用的模型来调整
                "messages": [
                    {
                        "role": "user",  # role: 作为助手角色，传递实际内容
                        "content": prompt
                    }
                ],
                "stream": False,
                "max_tokens": 8000,
                "stop": ["null"],  
                "temperature": 0,
                "top_p": 0.95,
                "top_k": 59,
                "frequency_penalty": 0.5,
                "n": 1,
                "response_format": {"type": "text"},
            }
            
            headers = {
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            }

            response = requests.request("POST", API_URL, json=payload, headers=headers)

            if response.status_code == 200:
                print(f"API call successful - Response status code: {response.status_code}")
                return response.json()['choices'][0]['message']['content'].strip()  # 根据返回结果格式调整
            else:
                print(f"API call failed - Response status code: {response.status_code}, Response: {response.text}")
                if attempt < max_retries - 1:
                    print(f"Waiting 5 seconds before retry {attempt + 2}...")
                    time.sleep(5)
                else:
                    print(f"Max retries reached for prompt. API Error {response.status_code}: {response.text}")
                    return None # Indicate failure after retries
        except requests.exceptions.RequestException as e: # More specific exception for network issues
            print(f"A network error occurred: {str(e)}")
            if attempt < max_retries - 1:
                print(f"Waiting 5 seconds before retry {attempt + 2}...")
                time.sleep(5)
            else:
                print(f"Max retries reached. Network error: {str(e)}")
                return None # Indicate failure after retries
        except Exception as e:
            print(f"An unexpected error occurred during API call: {str(e)}")
            if attempt < max_retries - 1:
                print(f"Waiting 5 seconds before retry {attempt + 2}...")
                time.sleep(5)
            else:
                print(f"Max retries reached. Unexpected error: {str(e)}")
                return None # Indicate failure after retries
    return None # Should be unreachable if loop completes, but as a fallback

def extract_text_from_docx(docx_path):
    """Extracts text from a .docx file."""
    try:
        doc = Document(docx_path)
        full_text = [para.text for para in doc.paragraphs]
        return "\n".join(full_text)
    except Exception as e:
        print(f"Error reading DOCX file {os.path.basename(docx_path)}: {e}")
        return None

def convert_pdf_to_txt_and_read(pdf_path, target_txt_path):
    """
    Converts a PDF file to a TXT file and returns the text content.
    The TXT file is created in the specified target_txt_path.
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            full_text = []
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    full_text.append(page_text)
            
            text_content = "\n".join(full_text)
            
        with open(target_txt_path, 'w', encoding='utf-8') as txt_file:
            txt_file.write(text_content)
        
        # print(f"Successfully converted '{os.path.basename(pdf_path)}' to '{os.path.basename(target_txt_path)}'")
        return text_content
        
    except Exception as e:
        print(f"Error converting PDF '{os.path.basename(pdf_path)}' to TXT or reading it: {e}")
        return None

def main():
    """Main function to process files and call API."""
    if not os.path.isdir(WORK_DIR):
        print(f"Error: Working directory not found: {WORK_DIR}")
        return

    os.chdir(WORK_DIR) # Change current working directory
    print(f"Working directory set to: {os.getcwd()}")

    prompt_template_path = os.path.join(WORK_DIR, PROMPT_TEMPLATE_FILENAME)
    try:
        with open(prompt_template_path, 'r', encoding='utf-8') as f:
            base_prompt_content = f.read().strip()
        if not base_prompt_content:
            print(f"Warning: The prompt file '{PROMPT_TEMPLATE_FILENAME}' is empty.")
    except FileNotFoundError:
        print(f"Error: Prompt file '{PROMPT_TEMPLATE_FILENAME}' not found in {WORK_DIR}. Please create it.")
        return
    except Exception as e:
        print(f"Error reading prompt file '{PROMPT_TEMPLATE_FILENAME}': {e}")
        return

    csv_file_path = os.path.join(WORK_DIR, OUTPUT_CSV_FILENAME)
    # Prepare CSV file and write headers if it's new or empty
    file_exists = os.path.isfile(csv_file_path)
    is_empty = not file_exists or os.path.getsize(csv_file_path) == 0
    
    try:
        with open(csv_file_path, 'a', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.writer(csvfile)
            if is_empty:
                writer.writerow(['名字', '总结'])
                print(f"Created new CSV file with headers: {OUTPUT_CSV_FILENAME}")
    except IOError as e:
        print(f"Error: Could not open or write to CSV file '{csv_file_path}': {e}")
        return

    # Keep track of files that have been processed to avoid reprocessing
    used_files = set()
    available_files_in_dir = sorted(os.listdir(WORK_DIR)) # Sort for deterministic file selection

    print(f"\nStarting processing for {len(NAMES_LIST)} entries...")
    for name_entry in tqdm(NAMES_LIST, desc="Processing entries"):
        names_in_entry = name_entry.split('\n') # Handles single names and groups
        
        # Name to write in CSV (original format, e.g., "陆子怡\n曾玉洁")
        name_for_csv = name_entry.replace("\n", " & ") # More readable in CSV if needed, or keep as is.
                                                       # Let's keep original for consistency with prompt.

        file_found_for_this_name_entry = False
        extracted_text = None
        
        # Try to find a matching file for the current name_entry
        for filename_in_dir in available_files_in_dir:
            if filename_in_dir in used_files:
                continue # Skip already processed files

            # Check if any name part from the current entry matches the filename
            match_found = False
            for part_name in names_in_entry:
                if part_name in filename_in_dir:
                    match_found = True
                    break
            
            if match_found:
                filepath = os.path.join(WORK_DIR, filename_in_dir)
                _, ext = os.path.splitext(filename_in_dir)
                print(f"\nProcessing file '{filename_in_dir}' for entry: '{name_for_csv}'")

                if ext.lower() == '.docx':
                    extracted_text = extract_text_from_docx(filepath)
                elif ext.lower() == '.pdf':
                    # Create a .txt filename based on the PDF filename
                    txt_filename_for_pdf = os.path.splitext(filename_in_dir)[0] + ".txt"
                    txt_filepath_for_pdf = os.path.join(WORK_DIR, txt_filename_for_pdf)
                    extracted_text = convert_pdf_to_txt_and_read(filepath, txt_filepath_for_pdf)
                else:
                    # Not a Word or PDF file, skip (or handle other types if needed)
                    # print(f"Skipping file '{filename_in_dir}' as it's not a .docx or .pdf.")
                    continue # Try next file in directory for this name_entry

                if extracted_text:
                    used_files.add(filename_in_dir)
                    file_found_for_this_name_entry = True
                    break # File processed for this name_entry, move to API call
                else:
                    print(f"Could not extract text from '{filename_in_dir}'. Trying next potential file for '{name_for_csv}'.")
                    # Continue searching for another file for this name_entry

        if not file_found_for_this_name_entry:
            print(f"\nWarning: No matching and readable file found for entry: '{name_for_csv}' in '{WORK_DIR}'. Skipping API call for this entry.")
            # Optionally write a placeholder to CSV or log this
            try:
                with open(csv_file_path, 'a', newline='', encoding='utf-8-sig') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow([name_entry, "Error: File not found or unreadable"])
            except IOError as e:
                print(f"Error: Could not write 'File not found' status to CSV for '{name_entry}': {e}")
            continue # Move to the next name_entry in NAMES_LIST

        if extracted_text:
            full_prompt = base_prompt_content + "\n\n--- Document Content ---\n" + extracted_text
            # print(f"Combined prompt for '{name_for_csv}':\n{full_prompt[:300]}...\n") # For debugging

            print(f"Calling API for entry: '{name_for_csv}'...")
            summary = call_siliconflow_api(full_prompt)

            if summary:
                print(f"API call successful for '{name_for_csv}'. Summary received.")
                try:
                    with open(csv_file_path, 'a', newline='', encoding='utf-8-sig') as csvfile:
                        writer = csv.writer(csvfile)
                        writer.writerow([name_entry, summary]) # Use original name_entry for CSV
                    print(f"Successfully wrote summary for '{name_for_csv}' to '{OUTPUT_CSV_FILENAME}'")
                except IOError as e:
                    print(f"Error: Could not write summary to CSV for '{name_entry}': {e}")
            else:
                print(f"API call failed or returned no summary for '{name_for_csv}'.")
                # Write error to CSV
                try:
                    with open(csv_file_path, 'a', newline='', encoding='utf-8-sig') as csvfile:
                        writer = csv.writer(csvfile)
                        writer.writerow([name_entry, "Error: API call failed or no summary"])
                except IOError as e:
                    print(f"Error: Could not write API failure status to CSV for '{name_entry}': {e}")
        else:
            # This case should ideally be caught by 'file_found_for_this_name_entry' check
            print(f"No text extracted for '{name_for_csv}', skipping API call.")
            try:
                with open(csv_file_path, 'a', newline='', encoding='utf-8-sig') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow([name_entry, "Error: No text extracted from file"])
            except IOError as e:
                print(f"Error: Could not write 'No text extracted' status to CSV for '{name_entry}': {e}")


    print(f"\nProcessing finished. Results saved to '{os.path.join(WORK_DIR, OUTPUT_CSV_FILENAME)}'")

if __name__ == "__main__":
    main()
