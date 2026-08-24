# Real-photo selection policy

Describe authentic photography that can plausibly be sourced from Pexels.
Avoid synthetic scenes, illustrations, surreal compositions, trademarks,
sensitive targeting, and AI-generated faces.

For each creative:

1. Name the desired emotion.
2. Choose one broad image category.
3. Produce one concrete English search query for a real candid or editorial
   photograph.
4. Choose left, center, or right crop focus based on where the subject should
   sit beneath the overlay.

The runtime searches up to ten square results, avoids reused photo IDs, checks
minimum dimensions and the Pexels CDN, downloads a supported bounded image,
and tries one broader category fallback. It then makes a deterministic crop,
gradient, typography, offer, and CTA overlay. Do not claim to have selected or
rendered the asset in model output.
