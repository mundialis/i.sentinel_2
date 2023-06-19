#!/usr/bin/env python3
############################################################################
#
# MODULE:       i.sentinel_2.parallel.index
# AUTHOR(S):    Guido Riembauer
#
# PURPOSE:      Calculates different indices in parallel.
# COPYRIGHT:    (C) 2020-2023 by mundialis GmbH & Co. KG and the GRASS Development Team
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
############################################################################

# %module
# % description: Calculates different indices and texture measures in parallel.
# % keyword: imagery
# % keyword: satellite
# % keyword: Sentinel
# % keyword: Index
# % keyword: parallel
# % keyword: NDVI
# % keyword: NDWI
# %end

# %option G_OPT_F_INPUT
# % key: red
# % label: Name of red band
# % required: no
# %end

# %option G_OPT_F_INPUT
# % key: nir
# % label: Name of NIR band
# % required: no
# %end

# %option G_OPT_F_INPUT
# % key: green
# % label: Name of green band
# % required: no
# %end

# %option G_OPT_F_INPUT
# % key: blue
# % label: Name of blue band
# % required: no
# %end

# %option G_OPT_F_INPUT
# % key: swir
# % label: Name of swir band
# % required: no
# %end

# %option G_OPT_M_DIR
# % key: output
# % description: Name for output index name
# % required: yes
# % guisection: Output
# %end

# %option
# % key: index
# % type: string
# % description: Index to be calculated
# % required: yes
# % options: NDVI,NDWI,NDBI,BSI,asm
# % multiple: no
# %end

# %option G_OPT_M_NPROCS
# % description: Number of cores for multiprocessing, -2 is n_cores-1
# % answer: -2
# % guisection: Optional
# %end

import os
import sys
import multiprocessing as mp
import atexit
import grass.script as grass

rm_rasters = []


def cleanup():
    nuldev = open(os.devnull, "w")
    kwargs = {"flags": "f", "quiet": True, "stderr": nuldev}
    for rmrast in rm_rasters:
        if grass.find_file(name=rmrast, element="raster")["file"]:
            grass.run_command("g.remove", type="raster", name=rmrast, **kwargs)


def main():
    global rm_rasters
    red = options["red"]
    green = options["green"]
    blue = options["blue"]
    nir = options["nir"]
    swir = options["swir"]
    index = options["index"]
    nprocs = int(options["nprocs"])
    output = options["output"]
    # set some common environmental variables, like:
    os.environ.update(
        dict(
            GRASS_COMPRESS_NULLS="1",
            GRASS_COMPRESSOR="ZSTD",
            GRASS_MESSAGE_FORMAT="plain",
        )
    )

    if not grass.find_program("r.mapcalc.tiled", "--help"):
        grass.fatal(
            _(
                "The 'r.mapcalc.tiled' module was not found, install it first:"
                "\ng.extension r.mapcalc.tiled"
            )
        )

    # test nprocs settings
    if nprocs > mp.cpu_count():
        grass.fatal(
            _(
                f"Using {nprocs} parallel processes but only "
                f"{mp.cpu_count()} CPUs available."
            )
        )

    if index == "NDVI":
        if not red and nir:
            grass.fatal(
                _(f"<red> and <nir> must be set for the index <{index}>")
            )
        grass.message(
            _(
                "Calculation of NDVI (Normalized difference vegetation index)..."
            )
        )
        formula = (
            f"{output} = round(255 * (1.0 + ({nir} - {red})/"
            f"float(({nir} + {red})))/2.0)"
        )

    elif index == "NDWI":
        grass.message(
            _("Calculation of NDWI (Normalized difference water index)...")
        )
        formula = (
            f"{output} = round(255 * (1.0 + ({green} - {nir})/"
            f"float(({green} + {nir})))/2.0)"
        )

    elif index == "NDBI":
        grass.message(
            _("Calculation of NDBI (Normalized difference built-up index)...")
        )
        formula = (
            f"{output} = round(255 * (1.0 + ({swir} - {nir})/"
            f"float(({swir} + {nir})))/2.0)"
        )

    elif index == "BSI":
        grass.message(_("Calculation of BSI (Bare soil index)..."))
        formula = (
            f"{output} = round(255 * (1.0 + (({swir} + {red})-({nir} + {blue}))"
            f"/float((({swir} + {red})+({nir} + {blue}))))/2.0)"
        )

    elif index == "asm":
        grass.message(_("Calculation of ASM (Angular Second Moment)..."))
        # First calculate pca1 of the four 10m bands (2,3,4,8) as input
        # for the texture calculation
        grass.message(_("Calculating PCA"))
        pca_name = f"pca_{os.getpid()}"
        rm_rasters.extend(
            [
                pca_name + ".1",
                pca_name + ".2",
                pca_name + ".3",
                pca_name + ".4",
            ]
        )
        grass.run_command(
            "i.pca", input=[blue, green, red, nir], output=pca_name, quiet=True
        )
        # Calculate texture - Angular Second Moment.
        # Window Size=3 results in larger differences between
        # urban and agricultural
        grass.message(_("Calculating Texture"))
        if nprocs > 1:
            grass.run_command(
                "r.texture.tiled",
                input=f"{pca_name}.1",
                method="asm",
                processes=nprocs,
                size=3,
                output=output,
                quiet=True,
            )
        else:
            grass.run_command(
                "r.texture",
                input=f"{pca_name}.1",
                method="asm",
                size=3,
                output=output,
                quiet=True,
            )
    else:
        grass.fatal(
            _(
                "Index not found. Please indicate one of the following:"
                " NDVI,NDWI,NDBI,BSI,asm"
            )
        )
    if index != "asm":
        if nprocs > 1:
            grass.run_command(
                "r.mapcalc.tiled",
                expression=formula,
                processes=nprocs,
                quiet=True,
            )
        else:
            grass.run_command("r.mapcalc", expression=formula, quiet=True)


if __name__ == "__main__":
    options, flags = grass.parser()
    atexit.register(cleanup)
    sys.exit(main())
