<div align="center">
<h1>SCALE4D</h1>
<h3>Metric 4D Modeling for Embodied Perception</h3>

<p>
  Di Liu<sup><img src="docs/assets/affiliations/meta.svg" alt="Meta" height="10"></sup> &nbsp;·&nbsp; Xuweiyi Chen<sup><img src="docs/assets/affiliations/meta.svg" alt="Meta" height="10"><img src="docs/assets/affiliations/uva.png" alt="University of Virginia" height="10"></sup> &nbsp;·&nbsp; Cheng Zhang<sup><img src="docs/assets/affiliations/meta.svg" alt="Meta" height="10"></sup> &nbsp;·&nbsp; Adam Harley<sup><img src="docs/assets/affiliations/meta.svg" alt="Meta" height="10"></sup> <br>
  Zhao Dong<sup><img src="docs/assets/affiliations/meta.svg" alt="Meta" height="10"></sup> &nbsp;·&nbsp; Tanner Schmidt<sup><img src="docs/assets/affiliations/meta.svg" alt="Meta" height="10"></sup> &nbsp;·&nbsp; David Caruso<sup><img src="docs/assets/affiliations/meta.svg" alt="Meta" height="10"></sup> &nbsp;·&nbsp; Pierre Moulon<sup><img src="docs/assets/affiliations/meta.svg" alt="Meta" height="10"></sup> <br>
  Shugao Ma<sup><img src="docs/assets/affiliations/meta.svg" alt="Meta" height="10"></sup> &nbsp;·&nbsp; Zezhou Cheng<sup><img src="docs/assets/affiliations/uva.png" alt="University of Virginia" height="10"></sup> &nbsp;·&nbsp; Richard Newcombe<sup><img src="docs/assets/affiliations/meta.svg" alt="Meta" height="10"></sup> &nbsp;·&nbsp; Jakob Julian Engel<sup><img src="docs/assets/affiliations/meta.svg" alt="Meta" height="10"></sup>
</p>

<p><img src="docs/assets/affiliations/meta.svg" alt="Meta" height="14"> Reality Labs Research, Meta &nbsp;·&nbsp; <img src="docs/assets/affiliations/uva.png" alt="University of Virginia" height="14"> University of Virginia</p>

<p>
  <a href="https://facebookresearch.github.io/rlr_scale4d/"><strong>Project Page</strong></a>
  &nbsp;·&nbsp;
  <a href="https://facebookresearch.github.io/rlr_scale4d/scale4d.pdf"><strong>Technical Report</strong></a>
  &nbsp;·&nbsp;
  <a title="Paper publication pending"><strong>Paper</strong></a>
  &nbsp;·&nbsp;
  <a href="https://facebookresearch.github.io/rlr_scale4d/demo.html"><strong>Demo</strong></a>
  &nbsp;·&nbsp;
  <a href="https://huggingface.co/facebook/SCALE4D" title="Model weights are under final legal review"><strong>Checkpoints</strong></a>
</p>

<img src=".github/assets/teaser.png" alt="SCALE4D metric 3D point trajectories in egocentric and robotic scenes" width="100%">
</div>

## Updates

- **Code and model weights are under final legal review and will be released very soon.**

## Overview

Metric 3D geometry and motion are essential for embodied reasoning.
Yet existing feedforward 4D models underuse synchronized views and calibrated
cameras available to embodied systems. We introduce **SCALE4D**, a unified
feedforward model that predicts metric 3D geometry and trajectories from single-
or multiview videos, with optional camera conditioning.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines and
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for our community standards.

## License

The majority of SCALE4D is licensed under CC-BY-NC 4.0, however portions of the
project are available under separate license terms: VideoMAE V2 is licensed
under the MIT license; three.js, used by the project website, is also licensed
under the MIT license.

See [LICENSE](LICENSE) for the SCALE4D license and
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for third party attribution and
license details.

Copyright (c) Meta Platforms, Inc. and affiliates.
