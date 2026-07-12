## DESCRIPTION

*i.sentinel_2.autotraining* is a GRASS addon that automatically creates
raster and vector training/validation data for further classification.
It covers the classes water, low vegetation, forest, bare soil and
built-up.

## EXAMPLE

```sh
i.sentinel_2.autotraining ndvi=ndvi ndwi=ndwi ndbi=ndbi bsi=bsi \
  ref_classification=PROBAV_classification_Borneo \
  ref_treecover_fraction=PROBA_V_100m_treecoverfraction \
  percentage_threshold=0.1 npoints=1000 output_vector=test_autotraining_vector \
  output_raster=test_autotraining_raster
```

## SEE ALSO

*[r.mapcalc](https://grass.osgeo.org/grass-stable/manuals/r.mapcalc.html),
[r.patch](https://grass.osgeo.org/grass-stable/manuals/r.patch.html),
[r.sample.category](https://grass.osgeo.org/grass-stable/manuals/addons/r.sample.category.html)*

## AUTHOR

Guido Riembauer, [mundialis GmbH & Co. KG](https://www.mundialis.de/)
