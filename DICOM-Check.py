import streamlit as st
import pydicom
from pydicom.uid import UID
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from io import BytesIO

st.title("DICOM Checker")

# 1. Ask the user to upload a DICOM file
uploaded_file = st.file_uploader("Upload a DICOM file")

if uploaded_file is not None:
    # Read the DICOM file
    dicom_data = pydicom.dcmread(BytesIO(uploaded_file.read()))

    # 2. Display the DICOM image
    if 'PixelData' in dicom_data:
        image = dicom_data.pixel_array
        st.subheader("DICOM Image")
        st.image(image, caption="DICOM Image", use_container_width=True, clamp=True)
    else:
        st.warning("No PixelData found in the DICOM file.")

    # 3. Display table with specified headers
    st.subheader("DICOM Header Information Check")

    # Extract required values
    ## Media Storage SOP Class
    sop_class_uid = dicom_data.file_meta.MediaStorageSOPClassUID
    sop_class_value = UID(sop_class_uid).name
    
    ## Transfer Syntax
    transfer_syntax_uid = dicom_data.file_meta.TransferSyntaxUID
    transfer_syntax_value = UID(transfer_syntax_uid).name

    ## Image Orientation Patient
    image_orientation_element = dicom_data.get((0x0020, 0x0037), None)
    image_orientation_value = (
    "Not found" if image_orientation_element is None else image_orientation_element.value
    )

    # Expected values
    expected_sop_class = "MR/CT/PET. Shouldn't be Secondary Capture Image"
    expected_transfer_syntax = "Explicit/Implicit VR Little Endian"
    expected_orientation_desc = "For CT: integers either 0 or +-1"

    # Build DataFrame for display
    table_data = [
        {"Code": "(0002,0002)","Header": "Media Storage SOP Class", "Value": str(sop_class_value), "Expected": expected_sop_class, "Solution if unexpected": "Image was created outside imaging device and cannot be used."},
        {"Code": "(0002,0010)","Header": "Transfer Syntax", "Value": str(transfer_syntax_value), "Expected": expected_transfer_syntax, "Solution if unexpected": "Image was compressed. Run the Decompression tool."},
    #    {"Code": "(0020,0037)","Header": "Image Orientation Patient", "Value": str(image_orientation_value), "Expected": expected_orientation_desc, "Solution if unexpected": "CT was acquired with gantry tilt and cannot be used"}
    ]
    df = pd.DataFrame(table_data)

    st.table(df)