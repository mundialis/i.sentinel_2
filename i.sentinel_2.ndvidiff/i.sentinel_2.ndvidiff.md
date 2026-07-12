## DESCRIPTION

*i.sentinel_2.ndvidiff* is a GRASS addon that calculates an NDVI
difference map from Sentinel-2 L2A data.

The goal of the addon is to compare the NDVI status from two time
intervals for an AOI given by the vector map *aoi*. For each interval,  
Sentinel-2 L2A data is imported from the local file system (using
[t.sentinel.import](https://github.com/mundialis/t.sentinel)) given
with\` input_dir_first\` and \`input_dir_second\`, cloud-masked (using
[t.sentinel.mask](https://github.com/mundialis/t.sentinel)),  
and temporally aggregated to receive one spectral band (using
[t.rast.mosaic](https://github.com/mundialis/t.rast.mosaic)) per time
interval.

One NDVI map for each time interval as well as a difference map between
the two are calculated. The user may define  
a threshold via the *ndvi_diff_threshold* option, which is used to
extract areas of signficant NDVI loss as raster and/or vector maps.  

The outputs of the module (RGBI mosaics, NDVI maps, NDVI difference map,
NDVI loss areas) can be saved as GRASS raster/vector maps or  
exported using the *output_dir* option.

## NOTES

The *offset* option can be used to take the systematic reflectance
offset into account that is added to Sentinel-2  
reflectance data since Processing Baseline 4.0.0.

If no *ndvi_diff_threshold* is given, a threshold is automatically
calculated from the NDVI difference map using  
*thresh = Q1 - 1.5 \* (Q3 - Q1)*, where Q1 and Q3 are the first and
third quantile of the NDVi difference map.

For cloud masking, the Sen2Cor cloud mask delivered with L2A data is
combined with the output of
[t.sentinel.mask](https://github.com/mundialis/t.sentinel).

The temporal aggregation method to be passed on to
[t.rast.mosaic](https://github.com/mundialis/t.rast.mosaic) can be
defined via the *aggregation_method* option.  
Best results were achieved with *minimum* aggregation which reduces
negative effects due to remaining clouds.

The *cloud_shadow_buffer* option can be used to define a buffer radius
(in raster cells) that is applied to detected  
clouds and cloud shadows to compensate for inaccuracies in the
cloud/shadow detection.

Cloud/Shadow masking is optional and is activated via the *-c* flag. If
visual inspection shows that all input S-2 scenes  
are cloudfree, it may be omitted.

The *nprocs* option can be used to run the different submodules in
parallel.

With the *min_size* option, small areas of detected NDVI loss may be
removed

The *rgbi_basename* option can be used to define a basename in case the
aggregated RGBI maps should be persistent in GRASS

A minimum NDVI value can be passed by the *relevant_min_ndvi* option. In
this case, identification of significant NDVI loss areas is  
delimited to pixels where the first aggregated NDVI map has a value of
at least *relevant_min_ndvi*.

## EXAMPLE

### Create an NDVI difference map in GRASS only, save intermediate results, skip cloud/shadow detection, use an automatic threshold for the detection of significant NDVi loss

```sh
i.sentinel_2.ndvidiff input_dir_first=~/S2_2020 input_dir_second=~/S2_2024 aoi=aoi_vector ndvi_loss_map_rast=ndvi_loss_result ndvi_diff_map=ndvi_diff_map_2024_2020 ndvi_map_first=ndvi_s2_2020 ndvi_map_second=ndvi_s2_2024 nprocs=4 offset=-1000 aggregation_method=minimum
```

### Export the NDVI difference map and intermediate results to a local directory, use a defined threshold, apply cloud masking and use a cloud/shadow buffer, apply a minimum size

```sh
i.sentinel_2.ndvidiff -c input_dir_first=~/S2_2020 input_dir_second=~/S2_2024 aoi=aoi_vector offset=-1000 nprocs=4 cloud_shadow_buffer=10 aggregation_method=minimum output_dir=~/result_dir ndvi_diff_threshold=-0.25 min_size=200
```

## REQUIREMENTS

\- [t.sentinel](t.sentinel.md), - [t.rast.mosaic](t.rast.mosaic.md) -
[grass-gis-helpers Python
module](https://github.com/mundialis/grass-gis-helpers)

## SEE ALSO

*[t.sentinel](t.sentinel.md), [t.rast.mosaic](t.rast.mosaic.md)*

## AUTHORS

Guido Riembauer, [mundialis](https://www.mundialis.de/)
