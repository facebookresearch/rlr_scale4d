# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.

"""Give the embedded 3D viewers (assets/gallery, assets/views, assets/camera) the page's look: a link to
assets/viewer-embed.css right after the viewer's own <style> block, written only in embed mode (?embed) and versioned
with the iframe's own v parameter, so the standalone viewer keeps its tuner look.

    python tools/theme_viewers.py      # patch the three published viewer pages in place (idempotent)

pack_gallery.py and pack_views.py call inject() on every rebuild."""
from pathlib import Path

MARK = "<!-- viewer-embed.css -->"
SNIPPET = (MARK + "<script>(function () { var q = new URLSearchParams(location.search); if (q.has(\"embed\")) "
           "document.write('<link rel=\"stylesheet\" href=\"' + new URL(\"../viewer-embed.css\", location.href).href + '?v=' + "
           "(q.get(\"v\") || \"0\") + '\">'); })();</script>\n")
# resolved against the page's own URL (location.href), not document.baseURI: the GitHub Pages copy of the gallery sets
# <base> to Hugging Face for its data files
ASSETS = Path(__file__).resolve().parent.parent / "assets"


def inject(page: str) -> str:
    if MARK in page:
        return page
    assert "</style>" in page, "viewer page without a <style> block"
    return page.replace("</style>", "</style>\n" + SNIPPET, 1)


if __name__ == "__main__":
    for name in ("gallery", "views", "camera"):
        p = ASSETS / name / "index.html"
        old = p.read_text(); new = inject(old)
        if new != old:
            p.write_text(new)
        print(p, "patched" if new != old else "already themed")
