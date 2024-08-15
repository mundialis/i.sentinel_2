#!/usr/bin/env python3
"""
############################################################################
#
# MODULE:      i.sentinel_2.ndvidiff
# AUTHOR(S):   Guido Riembauer

# PURPOSE:     Calculates NDVI difference maps from Sentinel-2 data
# COPYRIGHT:   (C) 2024 by mundialis GmbH & Co. KG
#              Team
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
#############################################################################
"""
# %Module
# % description: Calculates NDVI difference maps from Sentinel-2 data.
# % keyword: imagery
# % keyword: sentinel
# % keyword: ndvi
# %end

# %option G_OPT_M_DIR
# % key: input_dir_first
# % required: yes
# % description: Input directory that holds imagery from the first time interval
# %end

# %option G_OPT_M_DIR
# % key: input_dir_second
# % required: yes
# % description: Input directory that holds imagery from the second time interval
# %end

# %option G_OPT_V_INPUT
# % key: aoi
# % required: yes
# % description: Vector map that holds AOI area/s
# %end

# %option G_OPT_V_OUTPUT
# % key: ndvi_loss_map_vect
# % required: no
# % description: Output vector map that contains areas of NDVI loss
# %end

# %option G_OPT_R_OUTPUT
# % key: ndvi_loss_map_rast
# % required: no
# % description: Output raster map that contains areas of NDVI loss (intermediate result)
# %end

# %option G_OPT_R_OUTPUT
# % key: ndvi_diff_map
# % required: no
# % description: Output raster map that contains the NDVI difference map (intermediate result)
# %end

# %option G_OPT_R_OUTPUT
# % key: ndvi_map_first
# % required: no
# % description: NDVI raster map of the first time interval (intermediate result)
# %end

# %option G_OPT_R_OUTPUT
# % key: ndvi_map_second
# % required: no
# % description: NDVI raster map of the second time interval (intermediate result)
# %end

# %option
# % key: rgbi_basename
# % type: string
# % required: no
# % description: Basename to save aggregated RGBI-groups
# %end

# %option
# % key: output_dir
# % type: string
# % required: no
# % multiple: no
# % description: Output directory to write result files (RGBI/ndvi/loss rasters & vectors)
# %end

# %option
# % key: ndvi_diff_threshold
# % type: double
# % required: no
# % multiple: no
# % description: threshold to apply to NDVI difference map. If none is given, the threshold is calculated from the NDVI diff map using thr=Q1-1.5*(Q3-Q1)
# %end

# %option
# % key: relevant_min_ndvi
# % type: double
# % required: no
# % multiple: no
# % description: delimit identification of NDVI loss areas to pixels with an NDVI value of at least <relevant_min_ndvi> in the first time interval
# %end

# %option
# % key: nprocs
# % type: integer
# % required: no
# % answer: 1
# % multiple: no
# % description: Number of parallel processes to use
# %end

# %option
# % key: offset
# % type: integer
# % required: no
# % description: Offset to add to the Sentinel bands to due to specific processing baseline (e.g. -1000)
# %end

# %option
# % key: cloud_shadow_buffer
# % type: integer
# % required: no
# % answer: 5
# % description: Buffer in pixels to account for inacurracies in cloud/shadow masks
# %end

# %option
# % key: min_size
# % type: integer
# % required: no
# % description: Minimum size of detected ndvi loss areas (in map units)
# %end

# %option
# % key: aggregation_method
# % type: string
# % required: yes
# % options: average,count,median,mode,minimum,min_raster,maximum,max_raster,stddev,range,sum,variance,diversity,slope,offset,detcoeff,quart1,quart3,perc90,quantile,skewness,kurtosis
# % answer: minimum
# % description: temporal aggregation method used in t.rast.mosaic
# %end

# %flag
# % key: c
# % description: Run cloud masking (and mosaicking) using t.rast.mosaic/i.sentinel.mask
# %end

# %rules
# % required: output_dir,ndvi_loss_map_vect,ndvi_loss_map_rast

# import needed libraries
import atexit
import os
import grass.script as grass


# initialize global variables
rm_vec = []
rm_rast = []
rm_reg = []
rm_strds_w_rasters = []
rm_groups = []
cur_region = ""


# cleanup function (can be extended)
def cleanup():
    """Cleanup function (can be extended)"""
    from grass_gis_helpers import cleanup

    grass.run_command("g.region", region=cur_region)
    cleanup.general_cleanup(
        rm_vectors=rm_vec,
        rm_rasters=rm_rast,
        rm_regions=rm_reg,
        rm_strds_w_rasters=rm_strds_w_rasters,
        rm_groups=rm_groups,
        rm_mask=True,
    )


def main():
    """do the work"""
    from grass_gis_helpers import general

    global rm_vec, rm_rast, rm_reg, rm_strds_w_rasters, rm_groups, cur_region
    clouds = flags["c"]

    # check installed addons
    general.check_installed_addon("t.sentinel.import")
    general.check_installed_addon("t.sentinel.mask")
    general.check_installed_addon("t.rast.mosaic")
    general.check_installed_addon("t.rast.algebra")

    # check if output dir exists
    if options["output_dir"]:
        if not os.path.isdir(options["output_dir"]):
            try:
                os.makedirs(options["output_dir"])
            except Exception as e:
                grass.fatal(
                    _(f"Cannot create directory {options['output_dir']}: {e}")
                )

    # set region to AOI
    cur_region = f"cur_region_{os.getpid()}"
    rm_reg.append(cur_region)
    grass.run_command("g.region", save=cur_region)
    rm_reg.append(cur_region)
    grass.run_command("g.region", vector=options["aoi"], res=10, flags="a")

    # check nprocs
    nprocs = general.set_nprocs(options["nprocs"])

    # import
    in_dir1 = options["input_dir_first"]
    in_dir2 = options["input_dir_second"]

    ndvi_rasters = []
    output_rasters = []
    output_groups = []
    for x, in_dir in enumerate([in_dir1, in_dir2]):
        if not os.path.isdir(in_dir):
            grass.fatal(_(f"Directory {in_dir} does not exist"))
        scenes = os.listdir(in_dir)
        s2_scenes = [
            (
                True
                if scene.startswith("S2") and scene.endswith(".SAFE")
                else False
            )
            for scene in scenes
        ]
        if False in s2_scenes:
            if True in s2_scenes:
                grass.fatal(_(f"Both S2 and non-S2 scenes in {in_dir}"))
        if clouds:
            pattern = "B(02_1|03_1|04_1|08_1|8A_2|11_2|12_2)0m"
        else:
            pattern = "B(02_1|03_1|04_1|08_1)0m"
        # import to STRDS
        grass.message(_(f"Importing imagery data from {in_dir}"))
        strds_name = f"s2_timestep{x}"
        rm_strds_w_rasters.append(strds_name)

        import_kwargs = {
            "pattern": pattern,
            "input_dir": in_dir,
            "nprocs": nprocs,
            "strds_output": strds_name,
        }
        if options["offset"]:
            import_kwargs["offset"] = options["offset"]
        if clouds:
            import_kwargs["flags"] = "c"
            cloud_strds_sen2cor = f"{strds_name}_clouds_sen2cor"
            import_kwargs["strds_clouds"] = cloud_strds_sen2cor
            rm_strds_w_rasters.append(cloud_strds_sen2cor)
        grass.run_command("t.sentinel.import", quiet=True, **import_kwargs)

        if clouds:
            cloud_strds = f"{strds_name}_clouds_rast"
            shadow_strds = f"{strds_name}_shadows_rast"
            rm_strds_w_rasters.append(cloud_strds)
            rm_strds_w_rasters.append(shadow_strds)
            grass.message(
                _(f"Identifying clouds/shadows for S-2 data from timestep {x}")
            )
            grass.run_command(
                "t.sentinel.mask",
                input=strds_name,
                metadata="default",
                output_clouds=cloud_strds,
                min_size_clouds=0.05,
                min_size_shadows=0.05,
                output_shadows=shadow_strds,
                nprocs=nprocs,
            )

            # combine cloud masks from t.sentinel.mask and imported ones
            clouds_combined = f"{cloud_strds}_combined"
            rm_strds_w_rasters.append(clouds_combined)
            algexpression = (
                f"{clouds_combined} = "
                f"if(isntnull({cloud_strds}),0,"
                f"if(isntnull({cloud_strds_sen2cor}),0,null()))"
            )
            grass.run_command(
                "t.rast.algebra",
                nprocs=nprocs,
                basename="clouds_combined",
                expression=algexpression,
                flags="n",
                overwrite=True,
            )

        # prepare and run t.rast.mosaic
        grass.message(
            _(f"Temporally aggregating spectral bands for time step {x}...")
        )
        all_strds = list(grass.parse_command("t.list").keys())
        band_strds = [
            item.split("@")[0]
            for item in all_strds
            if item.startswith(f"{strds_name}_B")
        ]
        rm_strds_w_rasters.extend(band_strds)
        # use only r,g,b,nir
        rgb_nir_strds = []
        if options["rgbi_basename"] or options["output_dir"]:
            ref_list = ["B02", "B03", "B04", "B08"]
        else:
            # no need to calculate the other aggregations
            ref_list = ["B04", "B08"]
        for item in band_strds:
            if any(band in item for band in ref_list):
                rgb_nir_strds.append(item)
        for item in rgb_nir_strds:
            out_rast = f"{item}_aggregated"
            if not options["rgbi_basename"]:
                # in that case it is not needed in GRASS
                rm_rast.append(out_rast)
            t_rast_mosaic_kwargs = {
                "input": item,
                "output": out_rast,
                "method": options[
                    "aggregation_method"
                ],  # even if clouds are left, this should remove them
                # (but may add shadows)
                "granularity": "all",  # this produces a single raster
                # instead of a strds
                "nprocs": nprocs,
            }
            if "B02" in item:
                blue_band = out_rast
            elif "B03" in item:
                green_band = out_rast
            elif "B04" in item:
                red_band = out_rast
            elif "B08" in item:
                nir_band = out_rast

            if clouds:
                t_rast_mosaic_kwargs["clouds"] = clouds_combined
                t_rast_mosaic_kwargs["shadows"] = shadow_strds

                if options["cloud_shadow_buffer"]:
                    t_rast_mosaic_kwargs["cloudbuffer"] = options[
                        "cloud_shadow_buffer"
                    ]
                t_rast_mosaic_kwargs["shadowbuffer"] = options[
                    "cloud_shadow_buffer"
                ]
            grass.run_command(
                "t.rast.mosaic", overwrite=True, **t_rast_mosaic_kwargs
            )

        # create timestep group
        if options["rgbi_basename"]:
            timestep_group = f"{options['rgbi_basename']}_timestep{x}"
        else:
            timestep_group = f"rgbi_s2_timestep{x}"
            rm_groups.append(timestep_group)
        if options["output_dir"] or options["rgbi_basename"]:
            timestep_group_rasters = [
                red_band,
                green_band,
                blue_band,
                nir_band,
            ]
            grass.run_command(
                "i.group",
                group=timestep_group,
                input=timestep_group_rasters,
                quiet=True,
            )
            output_groups.append(timestep_group)

        # calculate NDVI
        grass.message(_(f"Calculating aggregated NDVI for time step {x}..."))
        if x == 0:
            if options["ndvi_map_first"]:
                ndvi_map = options["ndvi_map_first"]
            else:
                ndvi_map = f"{strds_name}_ndvi"
                rm_rast.append(ndvi_map)
        elif x == 1:
            if options["ndvi_map_second"]:
                ndvi_map = options["ndvi_map_second"]
            else:
                ndvi_map = f"{strds_name}_ndvi"
                rm_rast.append(ndvi_map)
        ndvi_rasters.append(ndvi_map)
        ndvi_exp = (
            f"{ndvi_map}=float({nir_band}-{red_band})/"
            f"({nir_band} + {red_band})"
        )
        grass.run_command("r.mapcalc", expression=ndvi_exp, quiet=True)

    grass.message(_("Calculating NDVI difference and loss maps..."))
    if options["ndvi_diff_map"]:
        ndvi_diff_map = options["ndvi_diff_map"]
    else:
        ndvi_diff_map = f"ndvi_diff_map_{os.getpid()}"
        rm_rast.append(ndvi_diff_map)

    ndvi_diff_exp = f"{ndvi_diff_map}={ndvi_rasters[1]}-{ndvi_rasters[0]}"
    grass.run_command("r.mapcalc", expression=ndvi_diff_exp, quiet=True)

    if options["ndvi_diff_threshold"]:
        ndvi_diff_threshold = options["ndvi_diff_threshold"]
    else:
        qs = grass.parse_command("r.univar", flags="ge", map=ndvi_diff_map)
        q1 = float(qs["first_quartile"])
        q3 = float(qs["third_quartile"])
        ndvi_diff_threshold = q1 - 1.5 * (q3 - q1)
    grass.message(_(f"NDVI loss threshold is set to {ndvi_diff_threshold}"))
    if options["ndvi_loss_map_rast"]:
        ndvi_loss_map = options["ndvi_loss_map_rast"]
    else:
        ndvi_loss_map = f"ndvi_loss_map_{os.getpid()}"
        rm_rast.append(ndvi_loss_map)

    grass.run_command("r.mask", vector=options["aoi"])
    if options["relevant_min_ndvi"]:
        loss_exp = (
            f"{ndvi_loss_map} = if(({ndvi_diff_map}<={ndvi_diff_threshold}"
            f" && {ndvi_rasters[0]}>={options['relevant_min_ndvi']}),1,null())"
        )
    else:
        loss_exp = (
            f"{ndvi_loss_map} = if({ndvi_diff_map}<="
            f"{ndvi_diff_threshold},1,null())"
        )
    grass.run_command("r.mapcalc", expression=loss_exp, quiet=True)
    if options["ndvi_loss_map_vect"]:
        ndvi_loss_map_vect = options["ndvi_loss_map_vect"]
    else:
        ndvi_loss_map_vect = f"{ndvi_loss_map}_vect"
        rm_vec.append(ndvi_loss_map_vect)

    ndvi_loss_map_vect_tmp = f"{ndvi_loss_map_vect}_tmp"
    rm_vec.append(ndvi_loss_map_vect_tmp)

    grass.message(_("Vectorizing results..."))
    grass.run_command(
        "r.to.vect",
        input=ndvi_loss_map,
        output=ndvi_loss_map_vect_tmp,
        type="area",
    )

    if options["min_size"]:
        grass.run_command(
            "v.clean",
            input=ndvi_loss_map_vect_tmp,
            output=ndvi_loss_map_vect,
            tool="rmarea",
            threshold=options["min_size"],
        )
    else:
        grass.run_command(
            "g.rename",
            vector=f"{ndvi_loss_map_vect_tmp},{ndvi_loss_map_vect}",
            quiet=True,
            overwrite=True,
        )

    if options["output_dir"]:
        out_dir = options["output_dir"]
        grass.message(_(f"Exporting result maps to {out_dir}"))
        output_rasters.extend(ndvi_rasters)
        output_rasters.append(ndvi_diff_map)
        output_rasters.extend(output_groups)
        for rast in output_rasters:
            outpath = os.path.join(out_dir, f"{rast}.tif")
            grass.run_command(
                "r.out.gdal",
                input=rast,
                output=outpath,
                createopt="COMPRESS=LZW,TILED=YES",
                overviews=5,
                flags="cm",
                quiet=True,
                overwrite=True,
            )
        outpath_vect = os.path.join(out_dir, f"{ndvi_loss_map_vect}.gpkg")
        grass.run_command(
            "v.out.ogr",
            input=ndvi_loss_map_vect,
            output=outpath_vect,
            quiet=True,
            overwrite=True,
        )


if __name__ == "__main__":
    options, flags = grass.parser()
    atexit.register(cleanup)
    main()
