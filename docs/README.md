# SCALE4D project page

Static site, no build step. Serve the folder with any web server (`file://` will not work, the page fetches its data):

    python -m http.server 8920 --bind 127.0.0.1

## GitHub Pages

This page is built from `XuweiyiChen/infd4rt`'s `website` branch by its `tools/sync_pages.py` (last sync
2026-11-24; first port at `2961cee`): `python tools/sync_pages.py <this docs folder>`, then commit here.

In **Settings → Pages**, select **Deploy from a branch**, branch **website**,
folder **/docs**, then **Save**. The site is served at
<https://facebookresearch.github.io/rlr_scale4d/> (private Pages: GitHub sign-in with access to this repository).
The `.nojekyll` file keeps the HTML, JavaScript, and other static assets unchanged during publishing.

For a local preview, run the server command above from this `docs/` directory.

Differences from the upstream branch, made by `tools/sync_pages.py`:

- Every 3D viewer's data is in this folder, the 74-scene gallery included, so the page needs no other host. To stay
  under GitHub Pages' 1 GB, input frames are WebP (quality 80) instead of JPEG, and files the page never requests are
  left out (the old Viewer4D scenes, the 2D comparison panels, the 160k side-by-side scenes, and the 1- and 2-view
  scenes of the zero-shot views section). The script stops if the folder reaches 990 MB. The same gallery is also
  archived in `facebook/SCALE4D` `examples/website_gallery` on Hugging Face.
- The footer links the license page (`license.html`, `LICENSE`, `LICENSES/`).
- `demo.json` holds the live demo's Gradio link, which `js/main.js` reads to show the Demo button and point it there
  (`demo.html` forwards to it as well). The demo's supervisor (`demo` branch of `infd4rt`,
  `evaluation/scale4d_demo/serve.py`) commits a new `demo.json` here and pushes it each time the link is renewed
  ("Update the live demo link" commits).

## License

The majority of SCALE4D is licensed under CC-BY-NC 4.0, however portions of the
project are available under separate license terms: VideoMAE V2 is licensed
under the MIT license; three.js is also licensed under the MIT license.

[Licenses](license.html) lists the applicable terms and links to the full,
unmodified license texts. Keep `LICENSE` and `LICENSES/` in this directory
synchronized with the repository's corresponding files.

## What is on the page

- Author names link to their personal sites or Google Scholar profiles. Affiliation marks use the paper's
  `assets/logometa.pdf` (the same infinity-symbol crop) and `assets/logouva.png`, exported to `assets/affiliations/`.
- The supplementary video appears at the end of section 01, before Explore in 4D. Its native player loads
  `examples/supplementary_video/video/scale4d_supplementary_v23_1440p.mp4` directly from `facebook/SCALE4D` on Hugging Face.
  The HF repository is public (not gated) since 2026-11-25. The player shows `assets/supp_poster.jpg`, the video's
  title card at 1.0 s, and loads the video's header at once (`preload="metadata"`; the file starts with its index,
  so playback starts without downloading the 143 MB first). The link below the player opens the video on Hugging
  Face. This video is not included in the Pages asset bundle.
- Benchmarks read `assets/data/results.json`, generated from the paper's LaTeX tables. Never type a score by hand.
- The comparison panels show the 160k checkpoint. The old Explore viewer (Viewer4D, `assets/scenes`, 160k) was replaced on 2026-11-12 by the gallery below; its files stay in the repo.
- The hero video is the apartment film v4.4 (textured GT room mesh, rigid tray), cut at 70.5 s, faces blurred with
  SAM 3 masks minus the false positives on the camera wearer's hand (/bigtemp/rqa8sm/website_v14/hero: make_hero.sh,
  blur_hero_v2.py). `assets/hero.mp4` is 1080p (crf 26, 27 MB) for windows at least 900 px wide, `assets/hero_720.mp4`
  (12 MB) for narrower ones (`<source media>`). The title stays; resting the pointer on the background for 3 s shows
  the film alone, and the title returns when the pointer leaves or the film ends.
- Aligned with the supplementary video v22 (2026-11-24, user: "都做 和video对齐"):
  - Explore in 4D opens with the video's 13 scenes (hand-object and robot clips together, then the in-the-wild captures),
    then its nine DAVIS clips (new "DAVIS" filter), then every earlier scene: `python tools/align_gallery_video.py` after
    pack_gallery.py. The video's scenes are its face-blurred files.
  - Faces: all 74 gallery scenes and card images are face-checked (SAM 3); 8 earlier scenes and 5 cards had faces and
    are blurred (staging and originals in /bigtemp/rqa8sm/website_faces_20261124). A pack_gallery.py rebuild restores
    the unblurred files, so re-run that pass after any rebuild.
  - Method shows the video's architecture figure (main_v21, the current paper labels).
  - Zero-shot multi view inference (formerly Beyond its training) offers 3-10 views only, like the video, and opens at
    3 views from its angle N2; the 1- and 2-view scenes stay in assets/views but have no button.
  - Text follows the video's cards (user: "这些text不是在video里面都改过了"): section titles "Zero-shot multi view
    inference", "Optional camera conditioning", "Metric 4D from any camera setup" (Method), "Camera-asymmetric
    self-training"; the 03 lead is the user's video line "Trained with at most 3 views, test on more views as input.";
    gallery kinds are the video's chapters (Robot Manipulation, Hand and Object Interaction, In the wild captures, plus
    DAVIS): `python tools/align_gallery_video.py --kinds`.
  - Self-training: the method figure on the left and the video's Ranch example on the right (controlled baseline |
    our self-training, cameras off, one camera and clock): `python tools/pack_views.py selftrain` -> assets/selftrain.
- Type and layout: section numbers sit above centered headings. Body copy and figure captions use a centered reading
  width of up to 860 px; figures, viewer groups, tabs, and scene cards are centered with their text. Below the hero,
  typography uses Instrument Sans, 500-weight headings, 18 px body copy, and smaller grey captions. Wide sections keep
  their full-width viewers. The embedded viewers take the
  same look from `assets/viewer-embed.css` (injected by `tools/theme_viewers.py`, which both pack scripts call).
- Loading: the department server sends no Cache-Control (mod_headers and mod_expires are unavailable; an `Expires`
  line in .htaccess gives a 500), so `sw.js` (registered from js/main.js as `sw.js?v=<V>`) caches every versioned
  request after its first download; videos and range requests bypass it. The deployed `.htaccess` gzips JSON, CSS and
  SVG (`AddOutputFilterByType DEFLATE`); HTML and JS are already gzipped by the server; scene .bin files do not
  compress. The 3D viewers start only when their section comes within 600-1200 px of the screen.
- Explore in 4D (section 02) embeds the published motion viewer (`assets/gallery`, SCALE4D 140k checkpoint): 65 scenes,
  the paper's Figure 5 cases and three ADT apartment clips with RGB + SLAM inputs first, then 54 picked by eye from
  786 previews of the square-crop runs (ADT, HOT3D, Aria, AgiBot, ABC, DROID, VITRA; previews, contact sheets and
  picks in /bigtemp/rqa8sm/scale4d_gallery_20261112). `assets/gallery/data` (1.8 GB) is not in git: rebuild it with
  the two commands in the table and deploy with rsync. Each scene keeps
  the settings of its paper render, with website trails starting at 24 frames. The synced input video is shown in the view;
  head-mounted clips (ADT, Forge)
  open in "Follow camera", a free view that moves with the input camera. Geometry and motion are predicted; multi-view
  clips take the dataset cameras. The scene cards use the paper renders.
- Beyond its training (03) and Cameras optional (04) follow the supplementary video v14 (2026-11-22): the video's
  examples come first and open at its camera angles (PStudio softball, angle C; ADT decoration, angle D, 6 degrees off
  the wall), with its bright ground truth (green fill, dark rim) and trails off; they play when on screen. Cameras
  optional shows cameras on | off side by side like the video, with one clock run by the page and one camera (the pane
  the visitor drags posts its view relative to its target camera and the other takes it). The earlier examples (Show3D
  can; DexYCB subjects 05 and 02) stay at their earlier angles. `python tools/pack_views.py [views] [camera]` rebuilds both.
- Section 06 is the arXiv's "Camera-Asymmetric Self-Training" (Sec. 3.4, 2026-11-22): its first paragraph, its
  Figure 4 (`figures/data_flywheel.pdf`, camera asymmetry only, rendered to `assets/fig/flywheel.jpg`) and its caption.
  The three-stage data-engine wheel was removed with it, because the arXiv no longer has a data-engine section.
- The overview is the arXiv abstract without its release sentence.
- Figures are the latest Internal paper's PDFs rendered to JPEG: teaser_v2, main_v3 (architecture), data_flywheel. Re-render them after the paper's figures change.
- The Paper button opens `scale4d.pdf`, the arXiv version of the paper (22 pages, 24 MB, added 2026-11-25). The arXiv
  button stays inactive until there is a link (`aria-disabled` in `index.html`).

## Regenerating assets

All paths below assume the infd4rt checkout with this branch as a worktree at `reference/website`.

| Asset | Command |
| --- | --- |
| Scores | `python tools/extract_tables.py [PAPER_REPO]` |
| Viewer scenes | `python tools/pack_scenes.py [KEY ...]` (edit `SCENES` for clips, views and captions) |
| Side-by-side 3D scenes | `python tools/pack_compare3d.py [KEY ...]` (assets/compare3d: every method on the same 112 x 112 subset of frame 0's lattice, shared Figure 4 view) |
| Comparison panels | from the infd4rt root: `python reference/website/tools/render_compare.py OUT KEY`, then `python tools/compress_compare.py OUT` |
| Hero video | `python tools/hero_from_film.py /bigtemp/rqa8sm/apartment_video_20261031/final/scale4d_apartment_v2_2k60.mp4` --end 70.5` for v2; the film is rendered by `evaluation/paper_figures/teaser_v5/apartment_film` |
| Earlier hero (studio segments) | `python tools/render_hero.py segment OUT KEY` (one per clip; set `CDP_PORT` when running in parallel), then join with ffmpeg `xfade` |
| Explore in 4D gallery | `/bigtemp/rqa8sm/scale4d_gallery_20261112/build.py` (exports the gallery site with the paper settings), then `python tools/pack_gallery.py` |
| Page check | `python tools/check_page.py` clicks through every control and fails on any page error or missing file |

The hero and check tools need headless Chrome, so run them on maxwell.

After changing any asset, bump `V` in `js/main.js` and the `?v=` strings in `index.html` (one value), or browsers keep
showing their cached copies: the department server sends no Cache-Control header.
- Side by Side (2026-11-24, user: "Side by Side make it better using our best checkpoints"): Ours is the released 140k
  checkpoint (`{key}_scale4d140k`, tools/pack_compare3d.py), Algorithm 1 on the same frames as the baselines; HOT3D with
  the dataset cameras, Aria Gen 2 with the recording's VIO poses (camera-off 140k let the cat clips' static scene slide
  ~19 cm), DROID with no cameras. The caption says what Ours sees. The 160k files (`_d4rt160ka1`) stay in assets.
- Overview figure = the paper's Figure 1 (`assets/fig/teaser_v2.jpg` from teaser_v2.pdf, caption from fig_teaser.tex);
  the earlier teaser.jpg is kept.
- Demo button: `demo.html` forwards to the live Gradio link, which the demo's supervisor (demo branch,
  evaluation/scale4d_demo/serve.py) writes to `demo.json` on the server (gitignored, never deployed from here).

