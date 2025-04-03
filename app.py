import streamlit as st
import os
import base64
import pandas as pd
from research.ocr.main import mistral_ocr
from research.matching.matching import data_matching
import tempfile
import os
import asyncio
import io

async def start_matching(csv_file_path, image_files_path):
    print(f"[mistral_ocr] Received folder_path: {image_files_path}") # DEBUG
    ocr_df = await mistral_ocr(image_files_path)
    assigned_df, unassigned_df = data_matching(csv_file_path, ocr_df)
    st.session_state.assigned_df = assigned_df
    st.session_state.unassigned_df = unassigned_df



st.set_page_config(page_title="Invoice Matcher", layout="wide")
st.title("🧾 Invoice Matching Tool 📄")

left_main, right_main = st.columns([2, 1])

with left_main:
    st.header("1. Upload Files")

    # Two columns for CSV & Receipt uploaders
    upload_col1, upload_col2 = st.columns(2)

    with upload_col1:
        st.subheader("🧾 Receipts (.jpg)")
        uploaded_receipts = st.file_uploader(
            "Select Receipt Images",
            accept_multiple_files=True,
            type=["jpg", "jpeg"],
            label_visibility="collapsed"
        )

    with upload_col2:
        st.subheader("📄 Statements (.csv)")
        uploaded_csvs = st.file_uploader(
            "Select Bank Statements",
            accept_multiple_files=True,
            type=["csv"],
            label_visibility="collapsed"
        )

    st.divider()
    st.header("2. Previews")

    st.subheader("🖼️ Receipts Preview")
    if uploaded_receipts:
        image_html_parts = []
        for file in uploaded_receipts:
            try:
                img_bytes = file.getvalue()
                encoded = base64.b64encode(img_bytes).decode()
                file_type = file.type
                html_part = f"""
                <div style="display: inline-block; width: 150px; margin: 0 4px; padding: 4px; 
                            text-align: center; vertical-align: top; background-color: #f8f9fa; 
                            border: 1px solid #dee2e6; border-radius: 4px; font-size: 0.9em;">
                    <img src="data:{file_type};base64,{encoded}" 
                         alt="{file.name}" 
                         style="max-width: 100%; height: 120px; 
                                object-fit: contain; display: block; margin-bottom: 4px;">
                    <p style="margin: 0; white-space: normal; word-wrap: break-word; 
                              line-height: 1.2;">{file.name}</p>
                </div>
                """
                image_html_parts.append(html_part)
            except Exception as e:
                st.warning(f"Could not process image {file.name}: {e}")

        if image_html_parts:
            all_images_html = "".join(image_html_parts)
            scrollable_container_html = f"""
            <style>
            .scrollable-container {{
                overflow-x:auto;
                white-space:nowrap;
                width:100%;
                padding:8px 4px;
                border:1px solid #ccc;
                border-radius:5px;
                background-color:#ffffff;
            }}
            </style>
            <div class="scrollable-container">{all_images_html}</div>
            """
            st.html(scrollable_container_html)
    else:
        st.info("Upload receipts to see preview.")

    st.subheader("📊 Statements Preview")
    if uploaded_csvs:
        for file in uploaded_csvs:
            try:
                st.write(f"**Preview: {file.name}**")
                df = pd.read_csv(file)
                st.dataframe(df.head(), height=150)
                file.seek(0)
            except Exception as e:
                st.error(f"Could not read or display {file.name}: {e}")
    else:
        st.info("Upload statements to see preview.")

@st.cache_data
def convert_df_to_excel(df):
    """Converts a Pandas DataFrame to an Excel file in-memory."""
    output = io.BytesIO()
    # Use ExcelWriter context manager for better handling
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
        # You could add more sheets here if needed:
        # df2.to_excel(writer, index=False, sheet_name='Sheet2')
    processed_data = output.getvalue()
    return processed_data

with right_main:
    st.header("Matching & Details")

    if st.button("Start Matching"):
        if uploaded_csvs and uploaded_receipts:
            # receipt_path = '/receipts3'
            # try:
            #     os.mkdir(receipt_path)
            # except FileExistsError:
            #     print('folder exists')
            with tempfile.TemporaryDirectory() as statements_tempdir:
                with tempfile.TemporaryDirectory() as receipts_tempdir:
                    for receipt_file in uploaded_receipts:
                        file_path = os.path.join(receipts_tempdir, receipt_file.name)
                        print(receipt_file.name)
                        with open(file_path, "wb") as f:
                            f.write(receipt_file.read())
                    #         print(f"--- Successfully wrote receipt: {file_path}") # DEBUG
                    # for file in glob.glob(receipt_path + '/*'):
                    #     print(f' donkey {file}' )

                    csv_file_path = os.path.join(statements_tempdir, uploaded_csvs[0].name)
                    with open(csv_file_path, "wb") as f:
                        f.write(uploaded_csvs[0].getvalue())
                    try:
                        loop = asyncio.get_running_loop()
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    loop.run_until_complete(start_matching(statements_tempdir, receipts_tempdir))
                    st.success("Matching process")
                    # Convert the DataFrame to Excel bytes
                    excel_data = convert_df_to_excel(st.session_state.assigned_df)


    st.divider()

    st.subheader("Select an Image to View Details")
    if uploaded_receipts:
        # List of all receipt image names
        receipt_names = [file.name for file in uploaded_receipts]

        selected_image = st.selectbox("Choose a receipt image", receipt_names)
        if selected_image:
            # Show placeholder for details
            st.write(f"**Details for:** {selected_image}")
            st.write("• Placeholder for date, vendor, total, etc.")
    else:
        st.info("No receipts available for selection.")

    st.divider()

    with st.subheader("Preview of export.xlsx"):
        if 'assigned_df' in st.session_state:
            st.dataframe(st.session_state.assigned_df)


st.subheader("Download as Excel")

if not st.session_state.assigned_df.empty:
    pass
else:
    st.download_button(
        label="📥 Download Excel File",
        data=excel_data,  # The bytes object to download
        file_name='assigned_data_download.xlsx',  # The default filename
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',  # Mime type for Excel files (.xlsx)
        help="Click to download the DataFrame as an Excel file"
    )

# st.markdown("---")
# st.write("Click the button above to download the data.")
