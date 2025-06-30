This Streamlit app is designed to help troubleshoot DICOM files that fail to import into ARIA.

- It displays a selected set of DICOM headers, along with their expected values and guidance on how to address discrepancies.
- It allows users to download the full DICOM header, including metadata, as a TXT file.
- If image data are present, the app will display the image.
- For DICOM files containing 3D imaging data, the app can split the file into individual slices and package them into a downloadable ZIP file.
- For compressed DICOM files, it provides a decompression tool, allowing the uncompressed files to be downloaded as a ZIP file.
