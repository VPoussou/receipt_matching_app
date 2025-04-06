import streamlit as st
import os
import base64
import pandas as pd
from research.ocr.main import mistral_ocr
from research.matching.matching import data_matching
import tempfile
import asyncio
import io

# Excel placeholder
excel_data = 'donkey'

# Async matcher
async def start_matching(csv_file_path, image_files_path):
    st.info("Running OCR & Matching...")
    ocr_df = await mistral_ocr(image_files_path)
    assigned_df, unassigned_df = data_matching(csv_file_path, ocr_df)
    st.session_state.assigned_df = assigned_df
    st.session_state.unassigned_df = unassigned_df

# Excel conversion
@st.cache_data
def convert_df_to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    return output.getvalue()

# Page config
st.set_page_config(page_title="Invoice Matcher", layout="wide")
st.title("🧾 Invoice Matching Tool 📄")

# -------------------- SIDEBAR (Collapsible Upload & Preview UI) --------------------
with st.expander("📁 Upload and Preview Section (Click to Collapse)", expanded=True):
    st.markdown("<h2 style='text-align:center;'>📤 Upload Files</h2>", unsafe_allow_html=True)

    # Upload UI
    uploaded_receipts = st.file_uploader(
        "🧾 Upload Receipt Images (.jpg, .jpeg)",
        accept_multiple_files=True,
        type=["jpg", "jpeg"]
    )

    uploaded_csvs = st.file_uploader(
        "📄 Upload Bank Statement CSVs",
        accept_multiple_files=True,
        type=["csv"]
    )

    st.markdown("---")
    st.markdown("<h2 style='text-align:center;'>👁️ Preview Files</h2>", unsafe_allow_html=True)

    # Receipt Preview
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

    # CSV Preview
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


# -------------------- MAIN UI (Right Side) --------------------
st.markdown("---")
with st.expander("🔍 Matching & Details)", expanded=True):
    # Start matching
    if st.button("🚀 Start Matching"):
        if uploaded_csvs and uploaded_receipts:
            with tempfile.TemporaryDirectory() as statements_tempdir, tempfile.TemporaryDirectory() as receipts_tempdir:
                for receipt_file in uploaded_receipts:
                    file_path = os.path.join(receipts_tempdir, receipt_file.name)
                    with open(file_path, "wb") as f:
                        f.write(receipt_file.read())

                csv_file_path = os.path.join(statements_tempdir, uploaded_csvs[0].name)
                with open(csv_file_path, "wb") as f:
                    f.write(uploaded_csvs[0].getvalue())

                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                loop.run_until_complete(start_matching(csv_file_path, receipts_tempdir))

                if 'assigned_df' in st.session_state:
                    st.session_state['excel_data'] = convert_df_to_excel(st.session_state.assigned_df)
                    st.success("✅ Matching Complete!")
        else:
            st.warning("Upload both a receipt image and a bank CSV first.")

    st.divider()
    # ----------- Separated Dropdowns for Matched & Unmatched -----------
    st.subheader("📸 View Receipt Details")
    if uploaded_receipts and 'assigned_df' in st.session_state:
        df = st.session_state.assigned_df
        uploaded_names = [file.name for file in uploaded_receipts]

        # Filter only uploaded images present in df
        filtered_df = df[df['assigned_picture'].isin(uploaded_names)]

        # --- Matched and Unmatched from existing df
        matched_set = set(filtered_df[filtered_df['checked'] == True]['assigned_picture'])
        unmatched_set_from_df = set(filtered_df[filtered_df['checked'] == False]['assigned_picture'])

        # --- Calculate unmatched by checking what was not matched at all (not even in df)
        uploaded_set = set(uploaded_names)
        all_found_set = set(filtered_df['assigned_picture'])
        unmatched_set_missing = uploaded_set - all_found_set

        # --- Final unmatched list (False matches + totally missing)
        unmatched_receipts = list(unmatched_set_from_df.union(unmatched_set_missing))
        matched_receipts = list(matched_set)

        # Layout
        col1, col2 = st.columns(2)

        # --- Helper
        def show_image_details(receipt_name, matched=True):
            for file in uploaded_receipts:
                if file.name == receipt_name:
                    st.image(file, caption=receipt_name, width=300)
                    break

            row = filtered_df[filtered_df['assigned_picture'] == receipt_name]
            if not row.empty:
                st.markdown(f"### {'✅ Matched Receipt' if matched else '❌ Not Matched'}: `{receipt_name}`")
                if not matched:
                    st.markdown("<div style='color:red;'>This receipt is not matched to any transaction.</div>", unsafe_allow_html=True)
                else:
                    st.write(f"• Date: {row['date'].iloc[0]}")
                    st.write(f"• Vendor: {row['vendor'].iloc[0]}")
                    st.write(f"• Amount: {row['amount'].iloc[0]:.2f}")
                    if 'match_score' in row.columns:
                        score = row['match_score'].iloc[0]
                        if pd.notna(score):
                            st.write(f"• Match Score: {score:.1f}%")
                    if 'match_type' in row.columns:
                        mtype = row['match_type'].iloc[0]
                        if pd.notna(mtype):
                            st.write(f"• Match Type: {mtype}")
            else:
                st.markdown("ℹ️ No data found for this image — it may not have been processed.", unsafe_allow_html=True)

        with col1:
            selected_matched = st.selectbox("✅ Matched Receipts", matched_receipts, key="matched_select")
            if selected_matched:
                show_image_details(selected_matched, matched=True)
        with col2:
            selected_unmatched = st.selectbox("❌ Unmatched Receipts", unmatched_receipts, key="unmatched_select")
            if selected_unmatched:
                show_image_details(selected_unmatched, matched=False)

    st.divider()

# Preview and Download
st.subheader("📄 Preview of export.xlsx")
if 'assigned_df' in st.session_state:
    st.dataframe(st.session_state.assigned_df)

st.subheader("⬇️ Download as Excel")
if 'excel_data' in st.session_state:
    st.download_button(
        label="📥 Download Excel File",
        data=st.session_state['excel_data'],
        file_name='assigned_data_download.xlsx',
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
else:
    st.info("No file ready yet.")
