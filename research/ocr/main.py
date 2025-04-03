import asyncio
from research.ocr.ocr_extraction import ocr_extraction  # Your OCR logic
import glob
import time
import pandas as pd

async def retrieve_data_from_images(folder_path, rate_limit=50, period=2):  #Images processed every 60 seconds (default)
    """
    Asynchronously retrieves data from images in a folder, respecting rate limits.
    Returns:
        dict: A dictionary where the keys are image file paths and the values are the extracted data.
    """

    all_data = {}
    semaphore = asyncio.Semaphore(rate_limit)  # Limit concurrent tasks

    async def process_image(file_path):
        async with semaphore:  # Acquire semaphore before processing
            start_time = time.time()
            try:
                data = await ocr_extraction(file_path)  # Await the async OCR extraction
                return file_path, data
            except Exception as e:
                print(f"Error processing {file_path}: {e}")
                return file_path, None  # Or handle the error as needed
            finally:
                elapsed_time = time.time() - start_time
                # Ensure that the execution takes at least the required time.
                sleep_time = period / rate_limit - elapsed_time
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time) # Add a delay for rate limiting



    tasks = [asyncio.create_task(process_image(file_path)) for file_path in glob.glob(folder_path + '/*.jpg')]

    for future in asyncio.as_completed(tasks):
        file_path, data = await future
        all_data[file_path] = data

    return all_data

async def mistral_ocr(folder_path):
    # nb_files = len(glob.glob(folder_path))
    # for file in glob.glob(folder_path):
    #     print(f'file = {file}')
    # print(f'received {folder_path} as folder_path with {nb_files} files')
    data_for_restructuring = await retrieve_data_from_images(folder_path)
    print(data_for_restructuring)
    wrong_keys = []
    for key, value in data_for_restructuring.items():
        if value == None:
            wrong_keys.append(key)
    for key in wrong_keys:
        data_for_restructuring.pop(key)
    structured_data = {
        'filename' : data_for_restructuring.keys(),
        'date_of_purchase' : [value.date_of_purchase for _, value in data_for_restructuring.items()],
        'name_of_store' : [value.name_of_store for _, value in data_for_restructuring.items()],
        'address' : [value.address for _, value in data_for_restructuring.items()],
        'total_price' : [value.total_price for _, value in data_for_restructuring.items()],
        'currency' : [value.currency for _, value in data_for_restructuring.items()],
    }
    df = pd.DataFrame(structured_data)
    return df