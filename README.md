<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/banner-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="assets/banner-light.svg">
  <img alt="Arnav Simha — machine learning, computational physics, molecular intelligence" src="assets/banner-dark.svg" width="100%">
</picture>

<br><br>

I build machine learning systems for scientific computing — models that have to respect physics, not just fit data.

Currently: LIFT-550 · Ryniant · retrosynthesis and turbulence

<a href="https://x.com/arnvsmh">X</a> · <a href="https://www.linkedin.com/in/arnvsmh">LinkedIn</a> · <a href="mailto:arnav@ryniant.com">Email</a>

</div>

## Selected work

<table>
<tr>
<td width="50%" valign="top">

### LIFT-550

Physics-informed super-resolution for wall-bounded turbulence. The finding is that the *training objective*, not the architecture, governs how much fine-scale content a model recovers — changing the loss moves reconstruction across a regime boundary that architecture changes don't cross.

First-author · In submission, SC26 AI4S Workshop (IEEE)

</td>
<td width="50%" valign="top">

### Ryniant

Retrosynthesis planning for pharmaceutical CROs. Route search over reaction graphs with GNN success scoring, layered over equipment feasibility, inventory, and quoting — so the routes a chemist gets back are ones their lab can actually run.

Founder · <a href="https://ryniant.com">ryniant.com</a>

</td>
</tr>
<tr>
<td width="50%" valign="top">

### YASUNet v2

The reconstruction model behind LIFT-550. Trained against multiple baselines with per-epoch component logging and band-resolved spectral error, so a gain in aggregate metrics can be traced to the wavenumber band it came from.

PyTorch · Turbulence · Spectral evaluation

</td>
<td width="50%" valign="top">

### Route Explorer

Radial visualization for synthesis routes: a bipartite molecule/reaction graph laid out from its own topology rather than fixed depth, so branch structure stays readable as routes get deep.

TypeScript · Graph layout

</td>
</tr>
</table>

## Systems

Python · C++ · CUDA · PyTorch · NumPy · RDKit · OpenFOAM · Docker · GCP

<div align="center">
<br>
<sub><code>research -> simulation -> discovery</code></sub>
</div>
