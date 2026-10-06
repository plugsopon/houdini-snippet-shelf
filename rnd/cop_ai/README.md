# FX AI in Copernicus (RND, 2026-10-06)

Generate AI images/videos from inside a COP network.

```
File COP (image)  ->  FX AI Angle  ->  FX AI Generate  ->  (result shows in the viewer)
                      orbit / elevation   Seedream 5 Pro (image) | Seedance 2.5 (video)
                      / distance          press Generate - runs in the background
```

- **FX AI Angle** - passes the image through; FX AI Generate reads its Orbit / Elevation /
  Distance from every Angle node above it and adds the camera words to the prompt.
- **FX AI Generate** - inputs: image, ref 1-3 (extra references for Seedream), prompt.
  **Any Wrangle wired into ANY input is the prompt**, not an image: its snippet text is read
  (`//` comment lines are stripped, so writing the prompt as comments keeps the Wrangle free of
  VEX errors; plain text also works - the Wrangle turns red, the generator does not care).
  Several prompt Wrangles join in input order, then the node's own Prompt field.
  Writes inputs + results to `$HIP/fxai_cop/<node>/` (`in_N.png`, `v001.png`, `v002.mp4`, ...).
  Every result is kept; pick an older one in *Result*. *History* keeps model, prompt, time per run.
- Token: `$REPLICATE_API_TOKEN`, else `~/.houdini_brother/replicate_token.txt`, else the
  Dremzo repo's `.env.local`. Never printed.

## Measured (hython 21.0.671 Apprentice)
- Seedream 5 Pro, 2K, orbit 45 / elevation 15 on the Oatside bottle: 124 s, result 1504x2672,
  product and label kept; elevation clearly followed, the 45 degree orbit only partly. `hip/cop_ai/compare_v001.jpg`
- Seedance 2.5 result path: the File COP reads an mp4 frame by frame (checked with an existing
  480p clip). The Seedance API call itself is NOT tested yet.
- The background thread + live status are written for the UI (hdefereval); hython runs blocking.

## Traps found
- **Apprentice refuses to SAVE Copernicus images above 1920x1080** (`rop_image` fails). Inputs are
  therefore read straight from `layer.allBufferElements()` (full res, float32, bottom-up rows,
  linear) and written to PNG with numpy+zlib - pixel-identical to the source (diff 0.0).
- A File COP has NO outputs until its AOVs exist (`addaovs` button, or set `aovs/aov1/type1`) -
  a fresh one created by script exports nothing.
- Spare parms on a subnet do not carry into `createDigitalAsset`; set them on the definition.

Rebuild: `hython rnd/cop_ai/build_fxai_cop.py` (writes `hip/cop_ai/fxai_cop_demo_v2.hipnc`, refuses to overwrite) (`--live` also presses Generate once = one paid call).

## Never reload the HDA inside a running Houdini
`hou.hda.reloadFile()` in Plug's live session crashed Houdini (signal 11, parm help tooltip on a
parm the reload removed). Rebuild in hython, then restart Houdini.
