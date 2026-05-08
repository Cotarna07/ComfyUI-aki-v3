from PIL import Image, ImageDraw, ImageFont
import imageio
import numpy as np
from skimage.color import rgb2gray
from skimage.feature import canny
from skimage.morphology import dilation
from scipy import ndimage as ndi
from skimage.measure import label, regionprops

# Read the image
im = imageio.imread('i1.jpg')

# Convert to grayscale
grayscale = rgb2gray(im)

# Detect edges using Canny edge detection
edges = canny(grayscale)

# Dilate edges to thicken them
thick_edges = dilation(dilation(edges))

# Fill holes in the binary image
segmentation = ndi.binary_fill_holes(thick_edges)

# Label connected components in the binary image
labels = label(segmentation)

# Function to check if bounding boxes overlap
def do_bboxes_overlap(a, b):
    return (
        a[0] < b[2] and
        a[2] > b[0] and
        a[1] < b[3] and
        a[3] > b[1]
    )

# Function to merge bounding boxes
def merge_bboxes(a, b):
    return (
        min(a[0], b[0]),
        min(a[1], b[1]),
        max(a[2], b[2]),
        max(a[3], b[3])
    )

# Extract properties of labeled regions
regions = regionprops(labels)
panels = []

# Merge overlapping bounding boxes
for region in regions:
    for i, panel in enumerate(panels):
        if do_bboxes_overlap(region.bbox, panel):
            panels[i] = merge_bboxes(panel, region.bbox)
            break
    else:
        panels.append(region.bbox)

# Remove small panels based on area threshold
for i, bbox in reversed(list(enumerate(panels))):
    area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
    if area < 0.01 * im.shape[0] * im.shape[1]:
        del panels[i]

# Function to check if bounding boxes are aligned along an axis
def are_bboxes_aligned(a, b, axis):
    return (
        a[0 + axis] < b[2 + axis] and
        b[0 + axis] < a[2 + axis]
    )

# Cluster bounding boxes based on alignment along an axis
def cluster_bboxes(bboxes, axis=0):
    clusters = []
    for bbox in bboxes:
        for cluster in clusters:
            if any(are_bboxes_aligned(b, bbox, axis=axis) for b in cluster):
                cluster.append(bbox)
                break
        else:
            clusters.append([bbox])

    clusters.sort(key=lambda c: c[0][0 + axis])

    for i, cluster in enumerate(clusters):
        if len(cluster) > 1:
            clusters[i] = cluster_bboxes(bboxes=cluster, axis=1 if axis == 0 else 0)

    return clusters

clusters = cluster_bboxes(panels)

# Create an image from the original array for drawing text on it
img = Image.fromarray(im)
draw = ImageDraw.Draw(img)
font_size = 160  # Set font size here
font = ImageFont.truetype('OpenSans-Bold.ttf', font_size)  # Ensure this font is available

def flatten(l):
    for el in l:
        if isinstance(el, list):
            yield from flatten(el)
        else:
            yield el

# Sort clusters top to bottom and right to left for numbering
sorted_clusters = sorted(flatten(clusters), key=lambda bbox: (bbox[0], -bbox[1]))

# Draw numbers on the image based on sorted bounding boxes
for i, bbox in enumerate(sorted_clusters, start=1):
    # Calculate text width using textlength method only for width.
    w = draw.textlength(str(i), font=font)
    
    # Use fixed height based on font size (this is an approximation)
    h = font_size  # Use the font size directly as height

    # Calculate coordinates for centered text within the bounding box
    x = (bbox[1] + bbox[3] - w) / 2  # Center horizontally in the bounding box (x-coordinates)
    y = (bbox[0] + bbox[2] - h) / 2  # Center vertically in the bounding box (y-coordinates)

    # Draw the text on the image with a specified color (gold)
    draw.text((x, y), str(i), fill=(255, 215, 0), font=font)

# Save or show the modified image with numbered labels
img.save("output_image.png")
img.show()