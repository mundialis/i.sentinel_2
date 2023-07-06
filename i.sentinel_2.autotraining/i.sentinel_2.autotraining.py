#!/usr/bin/env python3
#
############################################################################
#
# MODULE:      i.sentinel_2.autotraining
# AUTHOR(S):   Guido Riembauer, <riembauer at mundialis.de>
#
# PURPOSE:     Automatically generates training data from spectral indices and
#              a reference classification and treecover map.
#              Creates classes water, low vegetation, forest, bare soil and
#              built-up.
# COPYRIGHT:   (C) 2021-2023 by mundialis GmbH & Co. KG and the GRASS
#              Development Team
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
# %Module
# % description: Automatically generates training data from input bands and indices a reference classification and treecover map. Creates classes water, low vegetation, forest, bare soil and built-up.
# % keyword: imagery
# % keyword: satellite
# % keyword: Sentinel
# % keyword: classification
# % keyword: extraction
# %End

# %option G_OPT_R_INPUT
# % key: ndvi
# % type: string
# % required: yes
# % multiple: no
# % description: Input NDVI raster map
# %end

# %option G_OPT_R_INPUT
# % key: ndwi
# % type: string
# % required: yes
# % multiple: no
# % description: Input NDWI raster map
# %end

# %option G_OPT_R_INPUT
# % key: ndbi
# % type: string
# % required: yes
# % multiple: no
# % description: Input NDBI raster map
# %end

# %option G_OPT_R_INPUT
# % key: bsi
# % type: string
# % required: no
# % multiple: no
# % description: Input BSI raster map
# %end

# %option G_OPT_R_INPUT
# % key: ref_classification_probav
# % type: string
# % required: yes
# % multiple: no
# % description: Input reference probav classification map
# %end

# %option G_OPT_R_INPUT
# % key: ref_treecover_fraction_probav
# % type: string
# % required: yes
# % multiple: no
# % description: Input reference probav treecover fraction map
# %end

# %option G_OPT_R_INPUT
# % key: ref_classification_gong
# % type: string
# % required: no
# % multiple: no
# % description: Input reference gong et al. classification map
# %end

# %option G_OPT_R_INPUT
# % key: ref_ghs_built
# % type: string
# % required: yes
# % multiple: no
# % description: Input reference global human settlement builtup map (GHS-BUILT)
# %end

# %option
# % key: percentage_threshold
# % type: double
# % required: no
# % multiple: no
# % options: 0.0-50.0
# % answer: 0.1
# % description: Minimum percentage of area potential training data of a class has to cover to be included in the classification
# %end

# %option G_OPT_V_OUTPUT
# % key: output_vector
# % description: Output vector map with training data points. Class information will be stored in columns str_column and int_column
# %end

# %option G_OPT_R_OUTPUT
# % key: output_raster
# % description: Output raster map with potential training areas
# %end

# %option
# % key: str_column
# % type: string
# % required: no
# % multiple: no
# % answer: lulc_class_str
# % description: Name of the string column in output_vector to store class information
# %end

# %option
# % key: int_column
# % type: string
# % required: no
# % multiple: no
# % answer: lulc_class_int
# % description: Name of the integer column in output_vector to store class information
# %end

# %option
# % key: npoints
# % type: integer
# % required: yes
# % answer: 10000
# % label: Number of sampling points per class in the output vector map
# %end

import atexit
import os

import grass.script as grass

rm_rasters = []
TMP_MASK_OLD = None


def cleanup():
    """Cleaning up"""
    nulldev = open(os.devnull, "w")
    kwargs = {"flags": "f", "quiet": True, "stderr": nulldev}
    for rmrast in rm_rasters:
        if grass.find_file(name=rmrast, element="raster")["file"]:
            grass.run_command("g.remove", type="raster", name=rmrast, **kwargs)
    # remove possible masks
    if grass.find_file(name="MASK", element="raster")["file"]:
        grass.run_command("r.mask", flags="r")
    # reactivate potential old mask
    if TMP_MASK_OLD:
        grass.run_command("r.mask", raster=TMP_MASK_OLD, quiet=True)


def test_percentage(raster, reference_cells, percentage_threshold):
    """Test percentage of null value in raster"""
    n_raster = int(grass.parse_command("r.univar", map=raster, flags="g")["n"])
    if n_raster / reference_cells > percentage_threshold * 0.01:
        return True
    else:
        return False


def get_percentile(raster, percentile):
    """Function to return the Xth percentile of a raster"""
    return float(
        list(
            (
                grass.parse_command(
                    "r.quantile",
                    input=raster,
                    percentiles=percentile,
                    quiet=True,
                )
            ).keys()
        )[0].split(":")[2]
    )


def get_or_string(raster, values):
    """Function to generte or string"""
    return " || ".join([f"{raster} == {value}" for value in values])


def main():
    """Main function of the module"""
    global rm_rasters, TMP_MASK_OLD
    ndvi = options["ndvi"]
    ndbi = options["ndbi"]
    ndwi = options["ndwi"]
    bsi = options["bsi"]
    ref_class_probav = options["ref_classification_probav"]
    treecov = options["ref_treecover_fraction_probav"]
    ref_class_gong = options["ref_classification_gong"]
    ref_ghs_built = options["ref_ghs_built"]
    percentage_threshold = float(options["percentage_threshold"])
    output_vector = options["output_vector"]
    output_raster = options["output_raster"]
    npoints = options["npoints"]
    int_column = options["int_column"]
    str_column = options["str_column"]

    # output class nomenclature
    water = ("10", "water")
    low_veg = ("20", "low vegetation")
    forest = ("30", "forest")
    builtup = ("40", "built-up")
    baresoil = ("50", "bare soil")

    # classes are only kept if their possible training area covers at least
    # <percentage_threshold>% of the total area
    total_cells = int(
        grass.parse_command("r.univar", map=ndvi, flags="g")["n"]
    )
    output_classes = []
    training_rasters = []

    # find water training areas
    grass.message(_("Checking for water areas..."))
    water_cats_probav = ["80", "200"]
    water_cats_gong = ["60"]
    ndwi_percentile = "25"
    both_class_water = f"both_classifications_water_{os.getpid()}"
    rm_rasters.append(both_class_water)
    if ref_class_gong:
        exp_water1 = (
            f"{both_class_water} = if(("
            f"{get_or_string(ref_class_probav, water_cats_probav)}) && "
            f"{get_or_string(ref_class_gong, water_cats_gong)},1,null())"
        )
    else:
        exp_water1 = (
            f"{both_class_water} = if(("
            f"{get_or_string(ref_class_probav, water_cats_probav)}),1,null())"
        )

    grass.run_command("r.mapcalc", expression=exp_water1, quiet=True)
    grass.run_command("r.mask", raster=both_class_water, quiet=True)
    water_ndwi_perc = get_percentile(ndwi, ndwi_percentile)
    # ndwi_thresh_inref = '0.3'
    # ndwi_thresh_notinref = '0.8'
    water_raster = f"water_raster_{os.getpid()}"
    rm_rasters.append(water_raster)
    water_exp = (
        f"{water_raster} = if({ndwi} >= {water_ndwi_perc}, {water[0]}, null())"
    )
    grass.run_command("r.mapcalc", expression=water_exp, quiet=True)
    grass.run_command("r.mask", flags="r", quiet=True)
    if test_percentage(water_raster, total_cells, percentage_threshold):
        output_classes.append(water)
        training_rasters.append(water_raster)

    # find low vegetation training areas
    grass.message(_("Checking for low vegetation areas..."))
    lowveg_cats_probav = [
        "20",
        "30",
        "40",
        "100",
        "121",
        "122",
        "123",
        "124",
        "125",
        "126",
    ]
    lowveg_cats_gong = ["10", "30", "40", "50", "70"]
    ndvi_thresh_lowveg = 0.5
    treecov_max_lowveg = "25"  # previously: 50
    # ndvi_percentile_lowveg = '50'  # previously: 50
    tmp_lowveg_raster = f"lowveg_class_raster_{os.getpid()}"
    rm_rasters.append(tmp_lowveg_raster)
    if ref_class_gong:
        exp_lowveg1 = (
            f"{tmp_lowveg_raster} = if(("
            f"{get_or_string(ref_class_probav, lowveg_cats_probav)}) && ("
            f"{get_or_string(ref_class_gong, lowveg_cats_gong)}),1,0)"
        )
    else:
        exp_lowveg1 = (
            f"{tmp_lowveg_raster} = if(("
            f"{get_or_string(ref_class_probav, lowveg_cats_probav)}),1,0)"
        )
    grass.run_command("r.mapcalc", expression=exp_lowveg1, quiet=True)
    lowveg_mask_raster = f"lowveg_mask_raster_{os.getpid()}"
    rm_rasters.append(lowveg_mask_raster)
    eq_lowveg2 = (
        f"{lowveg_mask_raster} = if({tmp_lowveg_raster} == 1 && {treecov} <= "
        f"{treecov_max_lowveg},1,null())"
    )
    grass.run_command("r.mapcalc", expression=eq_lowveg2, quiet=True)
    grass.run_command("r.mask", raster=lowveg_mask_raster, quiet=True)
    lowveg_ndvi_median = get_percentile(ndvi, 50)
    if lowveg_ndvi_median > ndvi_thresh_lowveg:
        # in this case we can assume that mask contains a lot of vegetation
        # so we can set the threshold loosely
        ndvi_percentile_lowveg = "25"
    else:
        # in this case we can assume that the mask does not actually contain
        # a major part of vegetation, so we have to set a strict threshold
        ndvi_percentile_lowveg = "75"
    lowveg_ndvi_perc = get_percentile(ndvi, ndvi_percentile_lowveg)
    lowveg_raster = f"lowveg_raster_{os.getpid()}"
    rm_rasters.append(lowveg_raster)
    eq_lowveg3 = (
        f"{lowveg_raster} = if({ndvi} > {lowveg_ndvi_perc},"
        f"{low_veg[0]},null())"
    )
    grass.run_command("r.mapcalc", expression=eq_lowveg3, quiet=True)
    grass.run_command("r.mask", flags="r", quiet=True)
    if test_percentage(lowveg_raster, total_cells, percentage_threshold):
        output_classes.append(low_veg)
        training_rasters.append(lowveg_raster)

    # find forest training areas

    grass.message(_("Checking for forest areas..."))
    forest_cats_probav = [
        "111",
        "113",
        "112",
        "114",
        "115",
        "116",
        "121",
        "123",
        "122",
        "124",
        "125",
        "126",
    ]
    forest_cats_gong = ["20"]
    treecov_min_forest = "60"  # previously: 75
    ndvi_percentile_forest = "25"
    tmp_forest_raster = f"forest_class_raster_{os.getpid()}"
    rm_rasters.append(tmp_forest_raster)
    if ref_class_gong:
        exp_forest1 = (
            f"{tmp_forest_raster} = if(("
            f"{get_or_string(ref_class_probav, forest_cats_probav)}) && ("
            f"{get_or_string(ref_class_gong, forest_cats_gong)}),1,0)"
        )
    else:
        exp_forest1 = (
            f"{tmp_forest_raster} = if(("
            f"{get_or_string(ref_class_probav, forest_cats_probav)}),1,0)"
        )
    grass.run_command("r.mapcalc", expression=exp_forest1, quiet=True)
    forest_mask_raster = f"forest_mask_raster_{os.getpid()}"
    rm_rasters.append(forest_mask_raster)
    eq_forest2 = (
        f"{forest_mask_raster} = if({tmp_forest_raster} == 1 && "
        f"{treecov} >= {treecov_min_forest},1,null())"
    )
    grass.run_command("r.mapcalc", expression=eq_forest2, quiet=True)
    grass.run_command("r.mask", raster=forest_mask_raster, quiet=True)
    forest_ndvi_perc = get_percentile(ndvi, ndvi_percentile_forest)
    forest_raster = f"forest_raster_{os.getpid()}"
    rm_rasters.append(forest_raster)
    eq_forest3 = (
        f"{forest_raster} = if({ndvi} > {forest_ndvi_perc},{forest[0]},null())"
    )
    grass.run_command("r.mapcalc", expression=eq_forest3, quiet=True)
    grass.run_command("r.mask", flags="r", quiet=True)
    if test_percentage(forest_raster, total_cells, percentage_threshold):
        output_classes.append(forest)
        training_rasters.append(forest_raster)

    # find bare soil training areas
    grass.message(_("Checking for bare soil areas..."))
    # bare soil can also be part of low vegetation classes - we need to verify
    # later that training pixels don't mix

    baresoil_cats_probav = ["60", "40"]
    baresoil_cats_gong = ["10", "90"]
    treecov_max_baresoil = "25"  # previously: 50
    ndvi_threshold_baresoil = 0.3
    # ndvi_percentile_baresoil = '75'  # previously: 25, then 50/75
    bsi_percentile_baresoil = "25"  # previously: 75'

    tmp_baresoil_raster = f"baresoil_class_raster_{os.getpid()}"
    rm_rasters.append(tmp_baresoil_raster)
    if ref_class_gong:
        exp_baresoil1 = (
            f"{tmp_baresoil_raster} = if(("
            f"{get_or_string(ref_class_probav, baresoil_cats_probav)}) && ("
            f"{get_or_string(ref_class_gong, baresoil_cats_gong)}),1,0)"
        )
    else:
        exp_baresoil1 = (
            f"{tmp_baresoil_raster} = if(("
            f"{get_or_string(ref_class_probav, baresoil_cats_probav)}),1,0)"
        )
    grass.run_command("r.mapcalc", expression=exp_baresoil1, quiet=True)
    baresoil_mask_raster = f"baresoil_mask_raster_{os.getpid()}"
    rm_rasters.append(baresoil_mask_raster)
    eq_baresoil2 = (
        f"{baresoil_mask_raster} = if({tmp_baresoil_raster} == 1 && "
        f"{treecov} <= {treecov_max_baresoil},1,null())"
    )
    grass.run_command("r.mapcalc", expression=eq_baresoil2, quiet=True)
    grass.run_command("r.mask", raster=baresoil_mask_raster, quiet=True)
    baresoil_ndvi_median = get_percentile(ndvi, "50")
    if baresoil_ndvi_median < ndvi_threshold_baresoil:
        # in this case we can assume that a lot of the masked area is actually
        # bare soil, so we can set the threshold loosely
        ndvi_percentile_baresoil = "75"
    else:
        # here we can assume that there is some substantial part of vegetation
        # in the mask, so we have to set the threshold strict
        ndvi_percentile_baresoil = "25"
    baresoil_ndvi_perc = get_percentile(ndvi, ndvi_percentile_baresoil)
    baresoil_bsi_perc = get_percentile(bsi, bsi_percentile_baresoil)
    baresoil_raster = f"baresoil_raster_{os.getpid()}"
    rm_rasters.append(baresoil_raster)
    eq_baresoil3 = (
        f"{baresoil_raster} = if({bsi} >= {baresoil_bsi_perc} && "
        f"{ndvi} <= {baresoil_ndvi_perc},{baresoil[0]},null())"
    )
    grass.run_command("r.mapcalc", expression=eq_baresoil3, quiet=True)
    grass.run_command("r.mask", flags="r", quiet=True)
    if test_percentage(baresoil_raster, total_cells, percentage_threshold):
        output_classes.append(baresoil)
        training_rasters.append(baresoil_raster)

    # find built-up training areas
    grass.message(_("Checking for built-up areas..."))
    builtup_cats_probav = ["50"]
    # builtup_cats_gong = ["80"]
    builtup_thresh_ghs = "3"
    ndvi_percentile_builtup = "50"  # previously: 50, then 50
    ndbi_percentile_builtup = "50"  # previously: 75, then 50
    bu_mask_raster = f"builtup_mask_raster_{os.getpid()}"
    rm_rasters.append(bu_mask_raster)
    exp_builtup1 = (
        f"{bu_mask_raster} = if(("
        f"{get_or_string(ref_class_probav, builtup_cats_probav)}) && "
        f"({ref_ghs_built}>={builtup_thresh_ghs}),1,null())"
    )
    grass.run_command("r.mapcalc", expression=exp_builtup1, quiet=True)
    grass.run_command("r.mask", raster=bu_mask_raster, quiet=True)
    builtup_ndvi_perc = get_percentile(ndvi, ndvi_percentile_builtup)
    builtup_ndbi_perc = get_percentile(ndbi, ndbi_percentile_builtup)
    builtup_raster = f"builtup_raster_{os.getpid()}"
    rm_rasters.append(builtup_raster)
    eq_builtup = (
        f"{builtup_raster} = if({ndbi} >= {builtup_ndbi_perc} && "
        f"{ndvi} <= {builtup_ndvi_perc},{builtup[0]},null())"
    )
    grass.run_command("r.mapcalc", expression=eq_builtup, quiet=True)
    grass.run_command("r.mask", flags="r", quiet=True)
    if test_percentage(builtup_raster, total_cells, percentage_threshold):
        output_classes.append(builtup)
        training_rasters.append(builtup_raster)

    # merge training rasters
    classes_in_extent = [class_n[1] for class_n in output_classes]
    if len(classes_in_extent) == 0:
        grass.fatal(
            _(
                "No automatic training data generation possible. Not enough "
                "pixels match the requirements."
            )
        )
    elif len(classes_in_extent) == 1:
        grass.message(
            _(f"Only found one class in region: {classes_in_extent[0]}")
        )
        # in this case, no merging is necessary
        grass.run_command(
            "g.copy",
            raster=f"{training_rasters[0]},{output_raster}",
            quiet=True,
        )
    else:
        grass.message(
            _(f"Merging training data for classes {classes_in_extent}")
        )
        # make sure that pixels only belong to one class by masking
        tr_sum = f"tr_sum_{os.getpid()}"
        rm_rasters.append(tr_sum)
        tr_sum_eq = f"{tr_sum} ="
        for rast in training_rasters:
            tr_sum_eq += f"if( isnull({rast}), 0, 1 ) +"
        grass.run_command("r.mapcalc", expression=tr_sum_eq[:-2], quiet=True)
        # save MASK if there is one
        if grass.find_file(name="MASK", element="raster")["file"]:
            TMP_MASK_OLD = f"tmp_mask_old_{os.getpid()}"
            grass.run_command(
                "g.rename", raster=f"MASK,{TMP_MASK_OLD}", quiet=True
            )
        # create mask where the pixels belong only to one class
        tmp_mask_new = f"tmp_mask_new_{os.getpid()}"
        rm_rasters.append(tmp_mask_new)
        grass.run_command(
            "r.mapcalc",
            expression=f"{tmp_mask_new} = if({tr_sum} == 1, 1, null())",
            quiet=True,
        )
        grass.run_command("r.mask", raster=tr_sum, quiet=True)

        # test if there are enough pixels inside the training classes
        for rast in training_rasters:
            r_univar = grass.parse_command("r.univar", map=rast, flags="g")
            if int(r_univar["n"]) < int(npoints):
                grass.warning(
                    _(f"For <{rast}> only {r_univar['n']} pixels found.")
                )
        # patch it together
        grass.run_command(
            "r.patch", input=training_rasters, output=output_raster, quiet=True
        )
        grass.run_command("r.mask", flags="r", quiet=True)
        # reactivate mask if there was one before
        if TMP_MASK_OLD:
            grass.run_command("r.mask", raster=TMP_MASK_OLD, quiet=True)

    # extract points

    grass.message(_(f"Extracting {npoints} points per class..."))
    temp_output_column = output_raster.lower()
    # build table
    grass.run_command(
        "r.sample.category",
        input=output_raster,
        output=output_vector,
        npoints=npoints,
        quiet=True,
    )
    grass.run_command(
        "v.db.renamecolumn",
        map=output_vector,
        column=f"{temp_output_column},{int_column}",
        quiet=True,
    )
    grass.run_command(
        "v.db.addcolumn",
        map=output_vector,
        columns=f"{str_column} VARCHAR(25)",
        quiet=True,
    )
    for out_class in output_classes:
        grass.run_command(
            "v.db.update",
            map=output_vector,
            column=str_column,
            where=f"{int_column} = {out_class[0]}",
            value=out_class[1],
            quiet=True,
        )

    grass.message(_(f"Generated output training raster map <{output_raster}>"))
    grass.message(_(f"Generated output training vector map <{output_vector}>"))


if __name__ == "__main__":
    options, flags = grass.parser()
    atexit.register(cleanup)
    main()
