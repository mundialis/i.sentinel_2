[![image-alt](grass_logo.png)](https://grass.osgeo.org/grass-stable/manuals/index.html)

------------------------------------------------------------------------

## NAME

*i.sentinel_2* is a GRASS GIS addon toolset that searches, downloads,
imports and preprocesses multi-spectral Sentinel-2 satellite data from
the [ESA Copernicus
mission](https://www.esa.int/Applications/Observing_the_Earth/Copernicus).

## KEYWORDS

[imagery](https://grass.osgeo.org/grass-stable/manuals/imagery.html),
[import](https://grass.osgeo.org/grass-stable/manuals/topic_import.html),
[satellite](keywords.md#satellite), [Sentinel](keywords.md#Sentinel)

## DESCRIPTION

The *i.sentinel_2* toolset consists of currently four modules:

- [i.sentinel_2.autotraining](i.sentinel_2.autotraining.md):
  Automatically generates training data from spectral indices and a
  reference classification and treecover map
- [i.sentinel_2.parallel.index](i.sentinel_2.parallel.index.md):
  calculates different indices in parallel
- [i.sentinel_2.sen2cor](i.sentinel_2.sen2cor.md): runs atmospheric
  correction on a single Sentinel-2 L1C scene using sen2cor
- [i.sentinel_2.ndvidiff](i.sentinel_2.ndvidiff.md): Calculates NDVI
  difference maps from Sentinel-2 L2A data

## REQUIREMENTS

- *i.sentinel_2.sen2cor*: see
  [i.sentinel_2.sen2cor](i.sentinel_2.sen2cor.md) manual page

## AUTHORS

Guido Riembauer [mundialis GmbH & Co. KG](https://www.mundialis.de/),
Germany
