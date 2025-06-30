import streamlit as st
import pydicom
from pydicom.uid import (
    UID,
    generate_uid,
    MRImageStorage,
    CTImageStorage,
    ExplicitVRLittleEndian,
)
import numpy as np
import os
import matplotlib.pyplot as plt
import pandas as pd
import io
from io import BytesIO
from tempfile import TemporaryDirectory
import zipfile

# Manually define PET SOP Class UID (Standard UID for PET Image Storage)
PETImageStorage = "1.2.840.10008.5.1.4.1.1.128"


st.title("DICOM Checker")

#####################################################################
# Header check
st.subheader("DICOM Header Check")
# Ask the user to upload a DICOM file
uploaded_file = st.file_uploader("Upload a DICOM file")

if uploaded_file is not None:
    # Read the DICOM file
    dicom_data = pydicom.dcmread(BytesIO(uploaded_file.read()))

    # Display the DICOM image
    if 'PixelData' in dicom_data:
        image = dicom_data.pixel_array
        st.subheader("DICOM Image")
        if image.ndim == 2 or (image.ndim == 3 and dicom_data.SamplesPerPixel == 3):
            st.image(image, caption="DICOM Image", use_container_width=True, clamp=True)
        elif image.ndim == 3 and dicom_data.SamplesPerPixel == 1:
            st.success("The DICOM file contains a 3D image. The middle slice is displayed below")
            st.image(image[image.shape[0]//2,:,:], caption="DICOM Image", use_container_width=True, clamp=True)
        else:
            st.warning("PixelData cannot be displayed.")
    else:
        st.warning("No PixelData found in the DICOM file.")

    # Display table with specified headers
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
    expected_sop_class = "MR/CT/PET. Shouldn't be 'Secondary' or 'Enhanced'"
    expected_transfer_syntax = "Explicit/Implicit VR Little Endian"
    expected_orientation_desc = "For CT: integers either 0 or +-1"

    # Build DataFrame for display
    table_data = [
        {"Code": "(0002,0002)","Header": "Media Storage SOP Class", "Value": str(sop_class_value), "Expected": expected_sop_class, "Solution if unexpected": "'Secondary': Should not be used. 'Enhanced': Run the 3D splitting tool"},
        {"Code": "(0002,0010)","Header": "Transfer Syntax", "Value": str(transfer_syntax_value), "Expected": expected_transfer_syntax, "Solution if unexpected": "Image was compressed. Run the Decompression tool."},
    #    {"Code": "(0020,0037)","Header": "Image Orientation Patient", "Value": str(image_orientation_value), "Expected": expected_orientation_desc, "Solution if unexpected": "CT was acquired with gantry tilt and cannot be used"}
    ]
    df = pd.DataFrame(table_data)

    st.table(df)

    # Write header to a text file in memory
    dicom_header_str = str(dicom_data)
    header_bytes_io = io.BytesIO()
    header_bytes_io.write(dicom_header_str.encode("utf-8"))
    header_bytes_io.seek(0)

    # Allow user to download
    st.download_button(
        label="Download Full Header as Text File",
        data=header_bytes_io,
        file_name="dicom_header.txt",
        mime="text/plain"
    )

#####################################################################
# 3D splitting tool
st.subheader("3D Splitting Tool")

# File uploader
uploaded_file_3D = st.file_uploader("Upload a 3D DICOM file:")

if uploaded_file_3D:
    uploaded_file_3D.seek(0)  # Reset to the start of the stream
    #ds_3D = pydicom.dcmread(uploaded_file_3D, force=True)
    ds_3D = pydicom.dcmread(uploaded_file_3D)

    if ds_3D.pixel_array.ndim != 3:
        st.error("This is not a 3D file.")
    else:
        pixel_array_3d = ds_3D.pixel_array
        modality = ds_3D.get("Modality","Unknown")
        num_frames = pixel_array_3d.shape[0]
        st.success(f"3D DICOM file detected with {num_frames} frames.")

        # Determine output SOP Class UID based on modality
        if modality == "MR":
            write_sop_class = MRImageStorage
        elif modality == "CT":
            write_sop_class = CTImageStorage
        elif modality == "PT":
            write_sop_class = PETImageStorage
        else:
            st.error(f"Unsupported modality: {modality}")
            st.stop()

        # Split
        if st.button("Split into 2D slices"):
            with TemporaryDirectory() as tmpdir:
                output_dir = os.path.join(tmpdir, "Split")
                os.makedirs(output_dir, exist_ok=True)
               
                per_frame_element = ds_3D.get((0x5200, 0x9230), None)
                per_frame_seq = per_frame_element.value

                for i in range(num_frames):
                    new_ds = ds_3D.copy()

                    # Extract and assign single-frame pixel data
                    frame_pixels = pixel_array_3d[i]
                    new_ds.PixelData = frame_pixels.tobytes()
                    new_ds.Rows, new_ds.Columns = frame_pixels.shape

                    # EXTRACT REQUIRED INFO
                    new_ds.PixelSpacing = per_frame_seq[i].PixelMeasuresSequence[0].PixelSpacing
                    new_ds.SliceThickness = per_frame_seq[i].PixelMeasuresSequence[0].SliceThickness
                    new_ds.ImagePositionPatient = per_frame_seq[i].PlanePositionSequence[0].ImagePositionPatient
                    new_ds.ImageOrientationPatient = per_frame_seq[i].PlaneOrientationSequence[0].ImageOrientationPatient
                    if modality == "MR":
                        new_ds.ScanningSequence = "SE"
                        new_ds.SequenceVariant = "SK"
                    
                    # Remove multi-frame specific tags
                    for tag in ["NumberOfFrames","PerFrameFunctionalGroupsSequence", "SharedFunctionalGroupsSequence"]:
                        if tag in new_ds:
                            del new_ds[tag]
                    
                    # Update SOP UIDs
                    new_ds.SOPInstanceUID = generate_uid()
                    new_ds.SOPClassUID = write_sop_class
                    new_ds.file_meta.MediaStorageSOPClassUID = write_sop_class
                    new_ds.file_meta.MediaStorageSOPInstanceUID = new_ds.SOPInstanceUID

                    # Update Instance Number
                    new_ds.InstanceNumber = i + 1

                    # Save with instance number suffix
                    name_base, _ = os.path.splitext(uploaded_file_3D.name)
                    new_filename = f"{name_base}-slice{i+1:03}.dcm"
                    save_path = os.path.join(output_dir, new_filename)
                    new_ds.save_as(save_path)
                    
                st.success("3D file has been successfully split.")

                # Create zip
                zip_buffer = BytesIO()
                with zipfile.ZipFile(zip_buffer, "w") as zipf:
                    for root, _, files in os.walk(output_dir):
                        for file in files:
                            file_path = os.path.join(root, file)
                            zipf.write(file_path, arcname=file)
                zip_buffer.seek(0)

                st.download_button(
                    label="📁 Download All 2D Slices as ZIP",
                    data=zip_buffer,
                    file_name="2D_dicoms.zip",
                    mime="application/zip"
                )


#####################################################################
# Decompression tool
st.subheader("DICOM Decompression Tool")
# File uploader
uploaded_files = st.file_uploader(
    "Upload multiple compressed DICOM files:",
    # type=["dcm"],
    accept_multiple_files=True
)

if uploaded_files:
    # Decompress button
    if st.button("Decompress"):
        if not uploaded_files:
            st.warning("Please upload at least one DICOM file.")

        else:
            with TemporaryDirectory() as tmpdir:
                output_dir = os.path.join(tmpdir, "decompressed")
                os.makedirs(output_dir, exist_ok=True)

                for uploaded_file in uploaded_files:
                    try:
                        # Save uploaded file temporarily
                        file_path = os.path.join(tmpdir, uploaded_file.name)
                        with open(file_path, "wb") as f:
                            f.write(uploaded_file.read())

                        # Read and decompress
                        ds = pydicom.dcmread(file_path)
                        pixel_array = ds.pixel_array  # trigger decompression
                        ds.PixelData = pixel_array.tobytes()

                        # Set uncompressed format
                        ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
                        ds.is_implicit_VR = False
                        ds.is_little_endian = True

                        # Save with -decomp suffix
                        name, ext = os.path.splitext(uploaded_file.name)
                        new_name = f"{name}-decomp{ext or '.dcm'}"
                        save_path = os.path.join(output_dir, new_name)
                        ds.save_as(save_path)

                        st.success(f"✅ Decompressed: {new_name}")
                    except Exception as e:
                        st.error(f"❌ Failed: {uploaded_file.name} — {e}")

                # Create in-memory zip of decompressed files
                zip_buffer = BytesIO()
                with zipfile.ZipFile(zip_buffer, "w") as zipf:
                    for root, _, files in os.walk(output_dir):
                        for file in files:
                            file_path = os.path.join(root, file)
                            zipf.write(file_path, arcname=file)
                zip_buffer.seek(0)

                st.download_button(
                    label="📁 Download All Decompressed Files as ZIP",
                    data=zip_buffer,
                    file_name="decompressed_dicoms.zip",
                    mime="application/zip"
                )