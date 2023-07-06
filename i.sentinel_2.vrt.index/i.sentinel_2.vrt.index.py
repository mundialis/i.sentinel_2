#!/usr/bin/env python3
############################################################################
#
# MODULE:       i.sentinel_2.vrt.index
# AUTHOR(S):    Guido Riembauer
# PURPOSE:      Creates vrts from input rasters with identical Band suffix and
#               calculates indices parallelly.
# COPYRIGHT:    (C) 2020-2023 by mundialis GmbH & Co. KG and the
#               GRASS Development Team
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
# % description: Creates .vrt from input rasters and calculates different indices and texture measures in parallel.
# % keyword: imagery
# % keyword: satellite
# % keyword: Sentinel
# % keyword: Index
# % keyword: parallel
# % keyword: NDVI
# % keyword: NDWI
# %end

# %option G_OPT_F_INPUT
# % key: input
# % label: Input raster map names
# % description: Input raster map names. VRTs will be built based on same bands. The band must be indicated in a suffix of the raster, separated by an underscore, e.g. "_B4"
# % required: no
# %end

# %option
# % key: indices
# % type: string
# % required: no
# % multiple: yes
# % label: Indices (and texture measure) to be calculated. Required bands are imported automatically, even if not indicated in the bands option. Indicate 'None' for no indices
# % options: NDVI,NDWI,NDBI,BSI,asm,None
# % answer: NDVI,NDWI,NDBI,BSI,asm
# %end

# %option G_OPT_M_NPROCS
# % description: Number of cores for multiprocessing, -2 is n_cores-1
# % answer: -2
# % guisection: Optional
# %end

# %option
# % key: index_res
# % type: integer
# % required: no
# % multiple: no
# % label: Spatial resolution of indices to be calculated
# % answer: 10
# %end

# %option
# % key: prefix
# % type: string
# % required: no
# % multiple: no
# % description: Prefix in front of output maps
# %end

import grass.script as grass
import os
import sys
import multiprocessing as mp
import atexit
from grass.pygrass.modules import Module, ParallelModuleQueue

rm_regions = []


def cleanup():
    nuldev = open(os.devnull, "w")
    kwargs = {"flags": "f", "quiet": True, "stderr": nuldev}
    for rmr in rm_regions:
        if rmr in [x for x in grass.parse_command("g.list", type="region")]:
            grass.run_command("g.remove", type="region", name=rmr, **kwargs)
    # remove possible dangling temp_regions
    try:
        grass.del_temp_region()
    except Exception:
        grass.message(_("No temporary region found."))


def main():
    global rm_regions
    indices = options["indices"].split(",")
    nprocs = int(options["nprocs"])
    input = options["input"].split(",")
    prefix = options["prefix"]
    index_res = options["index_res"]

    if not grass.find_program("i.sentinel.parallel.index", "--help"):
        grass.fatal(
            _(
                "The 'i.sentinel_2.parallel.index' module was not found, install it first:"
                + "\n"
                + "g.extension i.sentinel_2.parallel.index url=path/to/addon"
            )
        )

    # set some common environmental variables, like:
    os.environ.update(
        dict(
            GRASS_COMPRESS_NULLS="1",
            GRASS_COMPRESSOR="ZSTD",
            GRASS_MESSAGE_FORMAT="plain",
        )
    )

    # test nprocs settings
    if nprocs > mp.cpu_count():
        grass.warning(
            _(
                "Using %d parallel processes but only %d CPUs available. Using %d procs."
            )
            % (nprocs, mp.cpu_count(), mp.cpu_count() - 1)
        )
        nprocs = mp.cpu_count() - 1

    # get unique bands
    vrt_list = []
    # get position of band info in filename
    for idx, item in enumerate(input[0].split("_")):
        if len(item) <= 4 and item.startswith("B"):
            bandinfo_idx = idx
    bands_complete = list(
        set([raster.split("_")[bandinfo_idx] for raster in input])
    )

    # generate vrts based on unique bands
    for band in bands_complete:
        current_bands_list = [
            item for item in input if item.split("_")[bandinfo_idx] == band
        ]
        vrt_name = prefix + band
        if len(current_bands_list) > 1:
            grass.run_command(
                "r.buildvrt",
                input=current_bands_list,
                output=vrt_name,
                overwrite=True,
            )
        elif len(current_bands_list) == 1:
            grass.message(
                _("Only one raster dataset found for band %s. Copying...")
                % (band)
            )
            rename_str = "%s,%s" % (current_bands_list[0], vrt_name)
            grass.run_command("g.copy", raster=rename_str, overwrite=True)
        else:
            grass.fatal(
                _("No raster datasets found for band %s. Cannot create vrt.")
                % (band)
            )
        vrt_list.append(vrt_name)

    # calculate indices
    if "None" not in indices:
        queue_index = ParallelModuleQueue(nprocs=nprocs)
        grass.use_temp_region()
        grass.run_command(
            "g.region", raster=vrt_list[0], res=index_res, flags="a"
        )
        for index in indices:
            outname = prefix + index
            nir = [vrt for vrt in vrt_list if vrt.endswith("8")][0]
            kwargs = {
                "index": index,
                "output": outname,
                "nprocs": 1,
                "nir": nir,
            }
            if index == "NDVI":
                red = [vrt for vrt in vrt_list if vrt.endswith("4")][0]
                kwargs["red"] = red
            elif index == "NDWI":
                green = [vrt for vrt in vrt_list if vrt.endswith("3")][0]
                kwargs["green"] = green
            elif index == "NDBI":
                swir = [vrt for vrt in vrt_list if vrt.endswith("11")][0]
                kwargs["swir"] = swir
            elif index == "BSI":
                swir = [vrt for vrt in vrt_list if vrt.endswith("11")][0]
                red = [vrt for vrt in vrt_list if vrt.endswith("4")][0]
                blue = [vrt for vrt in vrt_list if vrt.endswith("2")][0]
                kwargs["swir"] = swir
                kwargs["red"] = red
                kwargs["blue"] = blue
            elif index == "asm":
                green = [vrt for vrt in vrt_list if vrt.endswith("3")][0]
                red = [vrt for vrt in vrt_list if vrt.endswith("4")][0]
                blue_tmp = [vrt for vrt in vrt_list if vrt.endswith("2")]
                blue = [blue for blue in blue_tmp if not blue.endswith("12")][
                    0
                ]
                kwargs["green"] = green
                kwargs["red"] = red
                kwargs["blue"] = blue
            index_proc = Module(
                "i.sentinel_2.parallel.index", run_=False, **kwargs
            )
            queue_index.put(index_proc)
        queue_index.wait()
        grass.del_temp_region()


if __name__ == "__main__":
    options, flags = grass.parser()
    atexit.register(cleanup)
    sys.exit(main())
