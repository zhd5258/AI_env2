from __future__ import annotations

from typing import List, Tuple

import cv2
import numpy as np
import pypdfium2 as pdfium


def render_pdf_to_images(
    pdf_path: str,
    dpi: int = 300,
    max_pages: int | None = None,
    max_side: int = 4000,
    contrast: float = 1.0,
    sharpen: bool = False,
    page_range: str | None = None,
) -> List[Tuple[int, np.ndarray]]:
    scale = dpi / 72.0
    doc = pdfium.PdfDocument(pdf_path)
    num_pages = len(doc)
    images: List[Tuple[int, np.ndarray]] = []

    # Determine pages to process
    pages_to_process = []
    if page_range:
        pages_to_process = parse_page_range(page_range, num_pages)
    else:
        pages_to_process = list(range(num_pages))
    
    # Apply max_pages limit
    if max_pages is not None:
        pages_to_process = pages_to_process[:max_pages]

    for page_index in pages_to_process:
        if page_index >= num_pages:
            continue
            
        page = doc[page_index]
        bitmap = page.render(scale=scale, rotation=0)
        rgba = bitmap.to_numpy()
        bgr = cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGR)
        
        # Apply image enhancements if requested
        if contrast != 1.0:
            bgr = adjust_contrast(bgr, contrast)
        
        if sharpen:
            bgr = apply_sharpen(bgr)
        
        # downscale if longer side exceeds max_side
        h, w = bgr.shape[:2]
        long_side = max(h, w)
        if long_side > max_side:
            scale_ds = max_side / float(long_side)
            new_w = int(w * scale_ds)
            new_h = int(h * scale_ds)
            bgr = cv2.resize(bgr, (new_w, new_h), interpolation=cv2.INTER_AREA)
        images.append((page_index, bgr))

    return images


def parse_page_range(page_range: str, total_pages: int) -> List[int]:
    """Parse page range string and return list of page indices (0-based)"""
    if not page_range:
        return list(range(total_pages))
    
    pages = []
    ranges = page_range.split(',')
    
    for r in ranges:
        r = r.strip()
        if '-' in r:
            # Handle range like "1-5"
            start, end = r.split('-')
            start_idx = int(start) - 1  # Convert to 0-based
            end_idx = int(end) - 1      # Convert to 0-based
            
            # Ensure indices are within bounds
            start_idx = max(0, start_idx)
            end_idx = min(total_pages - 1, end_idx)
            
            # Add all pages in range
            pages.extend(range(start_idx, end_idx + 1))
        else:
            # Handle single page like "3"
            page_idx = int(r) - 1  # Convert to 0-based
            if 0 <= page_idx < total_pages:
                pages.append(page_idx)
    
    # Remove duplicates and sort
    return sorted(list(set(pages)))


def adjust_contrast(image: np.ndarray, factor: float) -> np.ndarray:
    """Adjust image contrast"""
    # Convert to LAB color space
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    
    # Apply contrast adjustment to L channel
    l = np.clip(l * factor, 0, 255).astype(np.uint8)
    
    # Merge channels and convert back to BGR
    enhanced = cv2.merge([l, a, b])
    result = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)
    return result


def apply_sharpen(image: np.ndarray) -> np.ndarray:
    """Apply image sharpening"""
    # Create sharpening kernel
    kernel = np.array([[-1, -1, -1],
                       [-1,  9, -1],
                       [-1, -1, -1]])
    
    # Apply sharpening filter
    sharpened = cv2.filter2D(image, -1, kernel)
    return sharpened