import os
import shutil
from ENTSOE.db_client import DbClient
from ENTSOE.extractor import Extractor

# --- CONFIGURATION ---
INPUT_DIRECTORY = "ExcelFilesNoProcessed"
PROCESSED_DIRECTORY = "ExcelFilesProcessed" 

if __name__ == "__main__":
    print("🚀 Starting massive data pipeline for TFG...")
    
    # Initialize database connection
    db_client = DbClient()
    
    # 1. Ensure directories exist
    if not os.path.exists(INPUT_DIRECTORY):
        os.makedirs(INPUT_DIRECTORY)
        print(f"📁 Created input folder: '{INPUT_DIRECTORY}'.")
        
    if not os.path.exists(PROCESSED_DIRECTORY):
        os.makedirs(PROCESSED_DIRECTORY)
        print(f"📁 Created archive folder: '{PROCESSED_DIRECTORY}'.")

    # 2. Process files
    input_files = os.listdir(INPUT_DIRECTORY)
    successfully_processed_count = 0
    
    for file_name in input_files:
        # Only process Excel or CSV files
        if file_name.endswith(".xlsx") or file_name.endswith(".csv"):
            source_path = os.path.join(INPUT_DIRECTORY, file_name)
            destination_path = os.path.join(PROCESSED_DIRECTORY, file_name)
            
            print(f"\n📄 Processing: {file_name}")
            
            try:
                # A. Extraction and cleaning
                extractor = Extractor(source_path)
                clean_data = extractor.process_entsoe_file()
                
                # B. MongoDB Ingestion
                if clean_data:
                    db_client.insert_prices(clean_data)
                    
                    # C. Move to processed folder
                    # If file already exists in destination, remove it first
                    if os.path.exists(destination_path):
                        os.remove(destination_path)
                    
                    shutil.move(source_path, destination_path)
                    print(f"📦 File moved to '{PROCESSED_DIRECTORY}'")
                    successfully_processed_count += 1
                else:
                    print(f"⚠️ File {file_name} did not contain valid data.")
                    
            except Exception as e:
                print(f"❌ Critical error processing {file_name}: {e}")

    # 3. Final summary
    if successfully_processed_count == 0:
        print(f"\n💡 No new files found to process in '{INPUT_DIRECTORY}'.")
    else:
        print(f"\n🏁 Pipeline complete. {successfully_processed_count} files moved to '{PROCESSED_DIRECTORY}'.")