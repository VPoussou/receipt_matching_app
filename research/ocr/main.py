import asyncio
from ocr_extraction import ocr_extraction  # Your OCR logic
import glob
import time

async def retrieve_data_from_images(folder_path, rate_limit=5, period=60):  #Images processed every 60 seconds (default)
    """
    Asynchronously retrieves data from images in a folder, respecting rate limits.
    Returns:
        dict: A dictionary where the keys are image file paths and the values are the extracted data.
    """

    all_data = {}
    semaphore = asyncio.Semaphore(rate_limit)  # Limit concurrent tasks

    async def process_image(file):
        async with semaphore:  # Acquire semaphore before processing
            start_time = time.time()
            try:
                data = await ocr_extraction(file)  # Await the async OCR extraction
                return file, data
            except Exception as e:
                print(f"Error processing {file}: {e}")
                return file, None  # Or handle the error as needed
            finally:
                elapsed_time = time.time() - start_time
                # Ensure that the execution takes at least the required time.
                sleep_time = period / rate_limit - elapsed_time
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time) # Add a delay for rate limiting



    tasks = [asyncio.create_task(process_image(file)) for file in glob.glob(folder_path + '*.jpg')]

    for future in asyncio.as_completed(tasks):
        file, data = await future
        all_data[file] = data

    return all_data

if __name__ == "__main__":
    async def main():
        """Main function to execute the image processing."""
        folder_path = './'
        rate_limit = 2 #Process 2 images
        period = 5 # every 5 seconds
        data = await retrieve_data_from_images(folder_path, rate_limit, period)
        print(data)

    asyncio.run(main())