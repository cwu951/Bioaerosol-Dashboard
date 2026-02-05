import subprocess
import os
import time
import pandas as pd
from datetime import datetime
import shutil
from pathlib import Path
from Constants import *

def load_existing_history():
    """Load existing historical data to prevent data loss after restart"""
    if AUTOMATION_FILE.exists():
        try:
            df = pd.read_csv(AUTOMATION_FILE)
            if 'Date' in df.columns and 'Time' in df.columns:
                print(f"Loaded {len(df)} rows from history.")
                return df
        except Exception as e:
            print(f"Error loading history: {e}")
    
    return pd.DataFrame(columns=["Date", "Time", "Bacteria", "Fungi", "Pollen", "PM2.5", "PM10"])

def check_input_files():
    """Check if the input directory contains the necessary AQ and FT files"""
    files = list(INPUT_DIR.glob("*"))
    has_aq = any("AQ_" in f.name for f in files)
    has_ft = any("FT_" in f.name for f in files)
    return has_aq and has_ft

def save_atomic(df, filepath):
    """Atomic write: write to a temporary file first, then rename"""
    temp_path = filepath.with_suffix('.tmp')
    df.to_csv(temp_path, index=False)
    os.replace(temp_path, filepath)

def main():
    print("=== Bioaerosol Automation Service Started ===")
    print(f"Watching Directory: {INPUT_DIR}")
    
    master_df = load_existing_history()
    
    while not check_input_files():
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Waiting for AQ and FT files in input directory...")
        time.sleep(10)
    
    print("Input files detected. Starting automation loop...")

    loop_count = 0
    
    while True:
        loop_start_time = datetime.now()
        timestamp_str = loop_start_time.strftime("%Y%m%d_%H%M%S")
        current_batch_filename = f"{FILENAME_PREFIX}_{timestamp_str}"
        
        print(f"\n--- Loop {loop_count} Start: {loop_start_time.strftime('%H:%M:%S')} ---")

        # Call R script
        cmd = [
            str(RSCRIPT_PATH),
            "bioaerosol_script.R",
            "-i", str(INPUT_DIR),
            "-o", str(TEMP_OUTPUT_DIR),
            "-f", current_batch_filename,
            "-t", TIME_INT
        ]
        
        try:
            print("Running R script...")
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            print(f"Error running R script: {e}")
            print(f"R Stderr: {e.stderr}")
            time.sleep(WAIT_TIME)
            continue

         # Read R results 
        expected_csv = TEMP_OUTPUT_DIR / f"{current_batch_filename}.csv"
        
        if expected_csv.exists():
            try:
                new_data = pd.read_csv(expected_csv)
                
                if not new_data.empty:
                    
                    # Handle long format output from R script
                    
                    # Check if R output contains necessary columns
                    required_r_cols = ['date', 'time', 'classification', 'conc']
                    if all(col in new_data.columns for col in required_r_cols):
                        
                        # Pivot data: Turn values in 'classification' column into column headers
                        pivoted_df = new_data.pivot_table(
                            index=['date', 'time'], 
                            columns='classification', 
                            values='conc', 
                            fill_value=0
                        ).reset_index()
                        
                        # Rename columns to match master_df
                        pivoted_df.rename(columns={'date': 'Date', 'time': 'Time'}, inplace=True)
                        
                        # Ensure all required columns exist
                        for col in ["Bacteria", "Fungi", "Pollen"]:
                            if col not in pivoted_df.columns:
                                pivoted_df[col] = 0.0
                        
                        # PM data (if supports PM in the future, adjustment is needed here)
                        # Current: keep as 0 
                        if "PM2.5" not in pivoted_df.columns:
                            pivoted_df["PM2.5"] = 0.0
                        if "PM10" not in pivoted_df.columns:
                            pivoted_df["PM10"] = 0.0
                            
                        # Keep only the needed columns 
                        final_cols = ["Date", "Time", "Bacteria", "Fungi", "Pollen", "PM2.5", "PM10"]
                        available_cols = [c for c in final_cols if c in pivoted_df.columns]
                        processed_batch = pivoted_df[available_cols]

                        # Merge and Save
                        
                        # Merge
                        combined_df = pd.concat([master_df, processed_batch], ignore_index=True)
                        
                        # Duplicate
                        master_df = combined_df.drop_duplicates(subset=['Date', 'Time'], keep='last')
                        master_df = master_df.sort_values(by=['Date', 'Time']).reset_index(drop=True)
                        
                        # Limit size
                        if len(master_df) > 5000:
                            master_df = master_df.iloc[-5000:]

                        # Save
                        save_atomic(master_df, AUTOMATION_FILE)
                        print(f"Success! Added {len(processed_batch)} new timestamps. Total records: {len(master_df)}")
                        
                    else:
                        print(f"Error: R output format unexpected. Columns found: {new_data.columns}")

                else:
                    print("R script produced empty data file.")
                
                # Clean up
                os.remove(expected_csv)
                
            except Exception as e:
                print(f"Error processing CSV data: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"Warning: Expected output file not found: {expected_csv}")

        loop_count += 1
        print(f"Sleeping for {WAIT_TIME} seconds...")
        time.sleep(WAIT_TIME)

if __name__ == "__main__":
    main()