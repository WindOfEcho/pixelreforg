# PixelReForge Core

Python image-processing core for PixelReForge.

Core must remain independent from API, Web UI, Docker, database, and desktop code. It exposes deterministic processing functions and data models that can be used by multiple interfaces.

## First restoration algorithm

The first working version targets pixel art that was enlarged by an integer nearest-neighbor scale.

Scale detection uses periodic boundary energy: it measures color differences between neighboring rows and columns, then checks which integer scale best concentrates those boundaries on a repeated grid. This works for clean 2x, 3x, and 4x enlarged pixel art and returns confidence metadata.

Restoration uses per-block majority vote. Each detected `scale_x` by `scale_y` block is reduced to one output pixel by selecting the most common color inside the block. This is deterministic and more stable than picking a single nearest-neighbor sample when minor noise is present.

The current real JPEG fixture is processed with a manual 4x override because compression noise hides the periodic grid from the first detector. Manual override is part of the MVP fallback path.

Later options to consider:

- Peak spacing over strong detected boundaries.
- Run-length analysis on quantized colors for noisy JPEG pixel art.
- Best-offset search for cropped or misaligned enlarged images.
- K-means or centroid color selection per block for anti-aliased sources.
- Autocorrelation or FFT period estimation for more robust scale detection.
