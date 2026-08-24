# Real-photo selection policy

Describe authentic photography that can plausibly be sourced from Pexels.
Avoid synthetic scenes, illustrations, surreal compositions, trademarks,
sensitive targeting, and AI-generated faces.

For each creative:

1. Name the desired emotion.
2. Define a concrete visual with direction, movement, meaningful symbolism,
   and immediate emotional clarity.
3. Choose one broad image category.
4. Produce one concrete English search query for a real candid or editorial
   photograph.
5. Choose left, center, or right crop focus based on where the subject should
   sit beneath the overlay.

Before accepting the creative direction, perform this semantic-alignment
self-check against the proposed image description and the selected hook:

1. **Emotion match** — the image's dominant emotion matches the headline.
2. **Narrative completion** — the image adds information the text does not.
3. **Specificity** — reject a visual that could fit five unrelated industries.
4. **Human tension** — an unresolved human moment is visible in the frame.
5. **Scroll test** — without text, the frame would still earn a half-second
   pause.

If a direction fails any gate, revise the image description/query or choose a
stronger headline candidate before returning the creative. The model evaluates
the proposed direction; it must not claim to have visually inspected the later
Pexels result.

The runtime searches up to ten square results, avoids reused photo IDs, checks
minimum dimensions and the Pexels CDN, downloads a supported bounded image,
and tries one broader category fallback. It then makes a deterministic crop,
gradient, typography, offer, and CTA overlay. Do not claim to have selected or
rendered the asset in model output.
