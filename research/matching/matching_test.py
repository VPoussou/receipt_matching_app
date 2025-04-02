import rapidfuzz.process as process # For finding the best match in a list
import rapidfuzz.fuzz as fuzz       # For specific scoring algorithms
import pandas as pd
import os
import numpy as np
from dateutil import parser
from datetime import timedelta, datetime # Import timedelta for date comparison

# --- Configuration ---
PATH_TO_CSV_FOLDER = "research/matching/bank_statements"
PATH_TO_OCR_EXPORT = "research/matching/export.csv"
PATH_TO_FINAL_OUTPUT = "research/matching/matched_bank_statement.csv"
PATH_TO_UNASSIGNED_LOG = "research/matching/unassigned_receipts.csv"
DATE_TOLERANCE_DAYS = 3 # How many days difference to allow for date matching
VENDOR_MATCH_THRESHOLD = 75 # Minimum similarity score (0-100) for vendor match

# --- Load Bank Statement Data ---
print("Loading bank statement data...")
df_list = []
for filename in os.listdir(PATH_TO_CSV_FOLDER):
    if filename.endswith(".csv"):
        try:
            current_df = pd.read_csv(os.path.join(PATH_TO_CSV_FOLDER, filename))
            # **Crucial: Identify and standardize bank statement columns here**
            # **Example:** Assuming columns are 'Transaction Date', 'Description', 'Amount'
            # You MUST adapt these lines based on your actual bank statement CSV structure
            current_df.rename(columns={
                'Transaction Date': 'date', # Standardize name
                'Description': 'vendor',    # Standardize name (might need cleaning later)
                'Amount': 'amount'         # Standardize name
            }, inplace=True, errors='ignore') # Ignore errors if columns don't exist
            df_list.append(current_df)
        except Exception as e:
            print(f"Error reading {filename}: {e}")

if not df_list:
    print(f"Error: No CSV files found or read successfully in '{PATH_TO_CSV_FOLDER}'. Exiting.")
    exit()

whole_df = pd.concat(df_list, ignore_index=True) # Use ignore_index with concat
print(f"Loaded {len(whole_df)} bank statement transactions.")

# --- Preprocess Bank Statement Data ---
print("Preprocessing bank statement data...")
# Convert amount to numeric, handling potential errors (e.g., currency symbols)
# Adapt this based on how amounts are formatted in your bank CSVs
whole_df['amount'] = pd.to_numeric(whole_df['amount'], errors='coerce')
# Convert date to datetime objects, handling potential errors
whole_df['date'] = pd.to_datetime(whole_df['date'], errors='coerce', dayfirst=False) # Adjust dayfirst if needed
# Ensure vendor is string
whole_df['vendor'] = whole_df['vendor'].astype(str).fillna('')
# Drop rows where essential info (date or amount) couldn't be parsed
whole_df.dropna(subset=['date', 'amount'], inplace=True)
print(f"{len(whole_df)} transactions remaining after preprocessing.")


# --- Load and Preprocess OCR Data ---
print("Loading and preprocessing OCR data...")
try:
    ocr_output = pd.read_csv(PATH_TO_OCR_EXPORT)
except FileNotFoundError:
    print(f"Error: OCR export file not found at '{PATH_TO_OCR_EXPORT}'. Exiting.")
    exit()
except Exception as e:
    print(f"Error reading OCR export file: {e}. Exiting.")
    exit()

# Define safe date parsing function (using your original logic but returning datetime)
def parse_date_safely_to_datetime(date_str):
    if pd.isna(date_str) or not isinstance(date_str, str):
        return pd.NaT # Return Not-a-Time for Pandas compatibility
    try:
        # Prefer dayfirst=False (MM/DD/YYYY or YYYY-MM-DD) unless sure otherwise
        dt = parser.parse(date_str, fuzzy=True, dayfirst=False)
        return dt
    except Exception:
        return pd.NaT

# Apply safe date parsing
ocr_output['parsed_date'] = ocr_output['date_of_purchase'].apply(parse_date_safely_to_datetime)

# Convert amount (already float from your code, but ensure numeric)
ocr_output['total_price'] = pd.to_numeric(ocr_output['total_price'], errors='coerce')

# Create combined vendor/address string, handling potential NaN values
ocr_output['vendor_address'] = ocr_output['name_of_store'].astype(str).fillna('') + ' ' + ocr_output['address'].astype(str).fillna('')
ocr_output['vendor_address'] = ocr_output['vendor_address'].str.strip() # Remove leading/trailing whitespace

# Clean filename
ocr_output['filename'] = ocr_output['filename'].astype(str).str.replace(r'^.*[\\/]', '', regex=True) # Handles both \ and /

# Drop OCR rows where essential info couldn't be parsed
ocr_output.dropna(subset=['parsed_date', 'total_price', 'filename'], inplace=True)
print(f"Loaded and preprocessed {len(ocr_output)} OCR entries.")


# --- Matching Logic ---
print("Starting matching process...")
# Initialize matching helper

# Add columns for results
whole_df['checked'] = False
whole_df['assigned_picture'] = pd.NA # Use Pandas NA for missing marker
whole_df['match_score'] = pd.NA # Optional: Store match score
whole_df['match_type'] = pd.NA # Optional: Store how it was matched

unassigned_pictures_list = []
date_tolerance = timedelta(days=DATE_TOLERANCE_DAYS)

# Iterate through each receipt (OCR output row)
for ocr_index, ocr_row in ocr_output.iterrows():
    picture_entry = ocr_row['filename']
    amount_entry = ocr_row['total_price']
    date_entry = ocr_row['parsed_date'] # Use the parsed datetime object
    vendor_entry = ocr_row['vendor_address']

    print(f"\nMatching Receipt: {picture_entry} (Amount: {amount_entry}, Date: {date_entry.strftime('%Y-%m-%d') if pd.notna(date_entry) else 'N/A'}, Vendor: {vendor_entry[:50]}...)")

    matched = False # Flag to check if we assigned this receipt

    # --- Step 1: Filter by Amount ---
    # Select only unchecked rows from the bank statement dataframe
    candidate_df = whole_df.loc[~whole_df['checked']].copy() # Work on a copy of unchecked rows
    amount_matches = candidate_df[candidate_df['amount'] == float(amount_entry)]

    print(f"  Found {len(amount_matches)} potential matches based on amount.")

    if amount_matches.empty:
        print(f"  No amount match found.")
        unassigned_pictures_list.append({ 'filename': picture_entry, 'reason': 'No amount match', 'amount': amount_entry})
        continue # Move to the next receipt

    if len(amount_matches) == 1:
        match_index = amount_matches.index[0]
        print(f"  Unique exact amount index {match_index}.")
        whole_df.loc[match_index, 'checked'] = True
        whole_df.loc[match_index, 'assigned_picture'] = picture_entry
        whole_df.loc[match_index, 'match_type'] = 'Exact Amount'
        whole_df.loc[match_index, 'match_score'] = 100 # Perfect score for exact match
        matched = True
        
        exact_date_matches = amount_matches[amount_matches['date'] == date_entry]
        print(f"  Found {len(exact_date_matches)} matches with exact amount and date.")

    elif len(exact_date_matches) == 1:
        # --- Step 2: Filter by Date (Exact Match) ---
        match_index = exact_date_matches.index[0]
        print(f"  Unique exact amount/date match found at index {match_index}.")
        whole_df.loc[match_index, 'checked'] = True
        whole_df.loc[match_index, 'assigned_picture'] = picture_entry
        whole_df.loc[match_index, 'match_type'] = 'Exact Amount/Date'
        whole_df.loc[match_index, 'match_score'] = 100 # Perfect score for exact match
        matched = True
    elif len(exact_date_matches) > 1:
        print(f"  Multiple exact amount/date matches. Proceeding to vendor match...")
        # Fall through to vendor matching below, using exact_date_matches as candidates
        candidates_for_vendor_match = exact_date_matches
        match_context = "Exact Amount/Date" # For logging/match_type
    else: # len(exact_date_matches) == 0
        # --- Step 3: Filter by Date (Nearby Match) ---
        print(f"  No exact date match. Checking within + {DATE_TOLERANCE_DAYS} days...")
        max_date = date_entry + date_tolerance
        nearby_date_matches = amount_matches[
            amount_matches['date'] <= max_date
        ]
        print(f"  Found {len(nearby_date_matches)} matches with exact amount and nearby date.")

        if len(nearby_date_matches) == 1:
            match_index = nearby_date_matches.index[0]
            print(f"  Unique nearby amount/date match found at index {match_index}.")
            whole_df.loc[match_index, 'checked'] = True
            whole_df.loc[match_index, 'assigned_picture'] = picture_entry
            whole_df.loc[match_index, 'match_type'] = 'Exact Amount / Nearby Date'
            # Score could reflect date proximity, but let's keep it simple
            whole_df.loc[match_index, 'match_score'] = 90 # High score for unique nearby date
            matched = True
        elif len(nearby_date_matches) > 1:
             print(f"  Multiple nearby amount/date matches. Proceeding to vendor match...")
             candidates_for_vendor_match = nearby_date_matches
             match_context = "Exact Amount / Nearby Date"
        else: # len(nearby_date_matches) == 0
            print(f"  No nearby date matches. Proceeding to vendor match on amount matches...")
            # Use all amount matches if no date matches found
            candidates_for_vendor_match = amount_matches
            match_context = "Exact Amount / No Date Match"

    # --- Step 4: Vendor/Address Fuzzy Match (if needed) ---
    # This block executes if 'matched' is still False and 'candidates_for_vendor_match' is not empty
    if not matched and not candidates_for_vendor_match.empty:
        print(f"  Performing vendor match using RapidFuzz on {len(candidates_for_vendor_match)} candidates...")
        vendor_list = candidates_for_vendor_match['vendor'].tolist()
        candidate_indices = candidates_for_vendor_match.index.tolist() # Original DataFrame indices

        # Ensure vendor_entry is a non-empty string for matching
        if vendor_entry and isinstance(vendor_entry, str):
            try:
                # Use rapidfuzz.process.extractOne to find the best match ABOVE the threshold
                # process.extractOne returns (choice, score, index_in_choice_list) or None
                best_match_tuple = process.extractOne(
                    vendor_entry,
                    vendor_list,
                    scorer=fuzz.WRatio,  # Weighted Ratio is often good for vendor names (handles token order)
                                        # Other good options: fuzz.ratio, fuzz.partial_ratio, fuzz.token_sort_ratio
                                        # Or fuzz.jaro_winkler_similarity if you prefer that metric
                    score_cutoff=VENDOR_MATCH_THRESHOLD # Only consider matches >= threshold
                )

                if best_match_tuple:
                    # Unpack the result
                    best_matching_vendor, score, list_index = best_match_tuple

                    # Get the original DataFrame index using the list_index
                    match_index = candidate_indices[list_index]

                    print(f"  Best vendor match found: '{best_matching_vendor}' (Score: {score:.2f}) at original index {match_index}.")
                    whole_df.loc[match_index, 'checked'] = True
                    whole_df.loc[match_index, 'assigned_picture'] = picture_entry
                    whole_df.loc[match_index, 'match_type'] = f'{match_context} / Vendor Match (RapidFuzz)'
                    whole_df.loc[match_index, 'match_score'] = score
                    matched = True

                else:
                    # extractOne returned None because no match met the score_cutoff
                    print(f"  No vendor match found above threshold {VENDOR_MATCH_THRESHOLD} using RapidFuzz.")
                    # Add to unassigned (check if reason already added in previous steps)
                    if not any(d['filename'] == picture_entry for d in unassigned_pictures_list):
                         unassigned_pictures_list.append({ 'filename': picture_entry, 'reason': f'No vendor match above threshold ({match_context})'})

            except Exception as e:
                print(f"  Error during RapidFuzz string matching: {e}")
                # Add to unassigned (check if reason already added)
                if not any(d['filename'] == picture_entry for d in unassigned_pictures_list):
                     unassigned_pictures_list.append({ 'filename': picture_entry, 'reason': f'RapidFuzz string matching error ({match_context})'})
        else:
            print(f"  Skipping vendor match because OCR vendor string is empty or invalid.")
            unassigned_pictures_list.append({ 'filename': picture_entry, 'reason': f'Invalid OCR vendor for matching ({match_context})'})

    # --- Final Check for Unassigned ---
    if not matched and not candidates_for_vendor_match.empty:
         # This case happens if vendor matching was attempted but failed to find a unique match above threshold
         print(f"  Receipt remains unassigned after all checks.")
         # Reason might already be added above, but double check if needed.
         # Check if it's already in the list to avoid duplicates if logic allows
         if not any(d['filename'] == picture_entry for d in unassigned_pictures_list):
              unassigned_pictures_list.append({ 'filename': picture_entry, 'reason': 'Failed vendor match or ambiguity'})


# --- Save Results ---
print("\nSaving results...")
try:
    whole_df.to_csv(PATH_TO_FINAL_OUTPUT, index=False, encoding='utf-8-sig') # Use utf-8-sig for better Excel compatibility
    print(f"Matched bank statement saved to '{PATH_TO_FINAL_OUTPUT}'")
except Exception as e:
    print(f"Error saving final output: {e}")

if unassigned_pictures_list:
    try:
        unassigned_df = pd.DataFrame(unassigned_pictures_list)
        unassigned_df.to_csv(PATH_TO_UNASSIGNED_LOG, index=False, encoding='utf-8-sig')
        print(f"List of {len(unassigned_df)} unassigned receipts saved to '{PATH_TO_UNASSIGNED_LOG}'")
    except Exception as e:
        print(f"Error saving unassigned receipts log: {e}")
else:
    print("All receipts were assigned successfully!")

print("\nMatching process completed.")