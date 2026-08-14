# ComfyUI workflow templates

Store API-format workflows here, versioned by engine and purpose. Do not mutate a
template by searching arbitrary JSON values at runtime. Each workflow must have a
small, explicit binding manifest mapping semantic inputs (prompt, seed, reference,
width, height, frames, output prefix) to node IDs and input names.

The first golden workflows will be captured only after LTX-2.5 and the chosen
image model run successfully on the target Mac. This avoids committing unverified,
hardware-incompatible graphs.
