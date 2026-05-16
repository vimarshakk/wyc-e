# Image Integration Testing Rules — WyshCare OCR

- Always use base64-encoded images for all tests and requests.
- Accepted formats: JPEG, PNG, WEBP only.
- Do not use SVG/BMP/HEIC.
- Do not upload blank or uniform-variance images.
- Every image must contain real visual features.
- Re-detect MIME after transformations (don't trust extensions).
- Animated formats (GIF/APNG/animated WEBP): extract first frame.
- Resize large images to reasonable bounds (<10 MB total payload).
