import streamlit as st
from PIL import Image, ImageDraw, ImageFont
import imageio
import numpy as np
from skimage.color import rgb2gray
from skimage.feature import canny
from skimage.morphology import dilation
from scipy import ndimage as ndi
from skimage.measure import label, regionprops
import easyocr

# Function to process the image and return segments
def process_image(image_path):
    im = imageio.imread(image_path)
    grayscale = rgb2gray(im)
    edges = canny(grayscale)
    thick_edges = dilation(dilation(edges))
    segmentation = ndi.binary_fill_holes(thick_edges)
    labels = label(segmentation)

    # Extract properties of labeled regions
    regions = regionprops(labels)
    panels = []

    # Merge overlapping bounding boxes
    for region in regions:
        panels.append(region.bbox)

    # Remove small panels based on area threshold
    for i, bbox in reversed(list(enumerate(panels))):
        area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
        if area < 0.01 * im.shape[0] * im.shape[1]:
            del panels[i]

    return panels, im

# Function to extract text from an image segment using EasyOCR
def extract_text(segment_image):
    reader = easyocr.Reader(['en'])
    text_results = reader.readtext(np.array(segment_image))
    return " ".join([text for (_, text, _) in text_results])

# Main function to run the Streamlit app
def main():
    st.title("Read Manga")

    # Specify the path to your input image
    image_path = 'yubi.jpg'  # Update this path if necessary

    # Process the image and get segments
    panels, original_image = process_image(image_path)

    # Initialize session state for current index and extracted texts if not already set
    if 'index' not in st.session_state:
        st.session_state.index = 0
        st.session_state.extracted_texts = []
        
        # Extract text for all segments and store them in session state
        for bbox in panels:
            segment_image = Image.fromarray(original_image[bbox[0]:bbox[2], bbox[1]:bbox[3]])
            text = extract_text(segment_image)
            st.session_state.extracted_texts.append(text)

    # Display the current segment if there are segments available
    if panels:
        bbox = panels[st.session_state.index]
        
        # Create a copy of the original image for drawing text on it
        segment_image = Image.fromarray(original_image[bbox[0]:bbox[2], bbox[1]:bbox[3]])
        
        # Draw bounding box number on the segment image
        draw = ImageDraw.Draw(segment_image)
        font_size = 40  # Set font size here
        font = ImageFont.truetype('OpenSans-Bold.ttf', font_size)  # Ensure this font is available

        # Draw the index number on the segment image (1-based index)
        # draw.text((10, 10), f"Segment {st.session_state.index + 1}", fill=(255, 215, 0), font=font)

        # Display the segment image with a caption indicating its number and total count
        st.image(segment_image, caption=f"Image {st.session_state.index + 1} of {len(panels)}", use_container_width=True)

        # Display extracted text for the current segment
        st.subheader("Text:")
        st.write(st.session_state.extracted_texts[st.session_state.index].lower())

        # Navigation buttons for next and previous segments
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Previous"):
                if st.session_state.index > 0:
                    st.session_state.index -= 1
        
        with col2:
            if st.button("Next"):
                if st.session_state.index < len(panels) - 1:
                    st.session_state.index += 1

if __name__ == "__main__":
    main()
