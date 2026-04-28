# Dynamic 3D Glacier Visualisation

Bachelor's thesis — computation of the velocity field of the Belvedere
glacier and visualisation of glacier motion in Blender.

**Year:** 2026

## Pipeline

Scripts are executed in the following order: `C1_bedrock.ipynb` → `C2_iceVelocity.ipynb ` → `C3_background.py ` → `C4_glacier.py`


### `C1_bedrock.ipynb` — Glacier bed reconstruction

Computes the glacier bed using the perfect-plasticity method
from digital elevation models (DEM) and polygonal outlines.

- Input: yearly glacier DEMs (.tif) + glacier outlines (.geojson)
- Output: `master_bedrock_mean.h5`

### `C2_iceVelocity.ipynb` — Ice velocity simulation

Computes the ice velocity field using the Shallow Stream Approximation (SSA)
with Picard iteration, complemented by internal deformation (SIA).

- Input: `master_bedrock_mean.h5`, DEM and outline for the selected year
- Output: GeoTIFFs for Blender in the `Blender_Input_<year>/` folder:
  - `SURFACE_<year>.tif` — smoothed surface
  - `SURFACE_RAW_<year>.tif` — raw DEM (input for Blender)
  - `BED_<year>.tif` — bedrock
  - `THICKNESS_<year>.tif` — ice thickness
  - `FLOW_<year>.tif` — velocity vector (R = Vx, G = Vy, m/year)

### `C3_background.py` — Blender: background visualisation

- Input: surrounding DEM, satellite image, alpha mask with cutout
- Output: Blender object `Background_Valley` with satellite texture

### `C4_glacier.py` — Blender: glacier animation (procedural texture)

Main animation script. Methods: semi-Lagrangian method with RK2 midpoint method

- Input: GeoTIFFs from `C2_iceVelocity.ipynb`
- Output: Blender scene ready for animation rendering


## Technologies used

- **Python 3.11.9** + Firedrake, icepack, rasterio, shapely, scipy, matplotlib
- **Blender 4.5.3 LTS**


## Licence
This project is licensed under the MIT License
