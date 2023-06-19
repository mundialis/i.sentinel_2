#!/usr/bin/env python3
#
############################################################################
#
# MODULE:      i.sentinel_2.sen2cor
# AUTHOR(S):   Guido Riembauer, <riembauer at mundialis.de>
#
# PURPOSE:     Runs atmospheric correction on a single Sentinel-2 L1C scene using sen2cor
# COPYRIGHT:   (C) 2021-2023 by Guido Riembauer, mundialis GmbH & Co. KG and the GRASS Development Team
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
#############################################################################

# %Module
# % description: Runs atmospheric correction on a single Sentinel-2 L1C scene using sen2cor.
# % keyword: imagery
# % keyword: satellite
# % keyword: Sentinel
# % keyword: atmospheric correction
# % keyword: radiometric conversion
# % keyword: radiance
# % keyword: reflectance
# % keyword: atmosphere
# %End

# %option G_OPT_F_INPUT
# % required: yes
# % key: input_file
# % label: Path to Sentinel-2 L1C dataset in .SAFE format
# %end

# %option
# % required: yes
# % key: output_dir
# % label: Output directory
# % type: string
# %end

# %option
# % key: sen2cor_path
# % required: yes
# % type: string
# % label: Path to sen2cor home directory
# % description: E.g. /home/user/sen2cor
# %end

# %option
# % key: aerosol_type
# % required: no
# % type: string
# % label: Aerosol model to use
# % options: rural,maritime,auto
# % answer: rural
# %end

# %option
# % key: season
# % required: no
# % type: string
# % label: Mid_latitude season
# % options: summer,winter,auto
# % answer: auto
# %end

# %option
# % key: ozone_content
# % required: no
# % type: integer
# % label: Ozone content in Dobson Unit (DU)
# % description: Use 0 to get best approximation from L1C metadata
# % answer: 0
# %end

# %option G_OPT_M_NPROCS
# % label: Number of parallel processes used for band importing in sen2cor
# % description: Number of cores for multiprocessing, -2 is n_cores-1
# % answer: -2
# %end

# %flag
# % key: r
# % description: Remove input folder after successful completion
# %end

import atexit
import os
from pathlib import Path
import shutil
import subprocess
import multiprocessing as mp
import xml.etree.ElementTree as ET

from grass.script import core as grass

rm_files = []
rm_folders = []
rel_dem_dir = None
sen2cor_dir = None


def cleanup():
    for rmfile in rm_files:
        try:
            os.remove(rmfile)
        except Exception as e:
            grass.warning(_(f"Unable to remove file {rmfile}: {e}"))
    # remove DEM
    # find dem_folder, it can be in different folders depending on version.
    # for whatever reason it can also be in the home directory rather than
    # the installed sen2cor directory
    possible_dirs_all = [
        sen2cor_dir,
        os.path.join(str(Path.home()), "sen2cor"),
        os.path.join("root", "sen2cor"),
    ]
    possible_dirs = list(set(possible_dirs_all))
    for possible_dir in possible_dirs:
        for root, dir, files in os.walk(possible_dir):
            if rel_dem_dir in root:
                rm_folders.append(root)
    for rmfolder in rm_folders:
        try:
            shutil.rmtree(rmfolder)
        except Exception as e:
            grass.warning(_(f"Unable to remove folder {rmfolder}: {e}"))


def main():
    global rm_files, rm_folders, rel_dem_dir, sen2cor_dir
    sen2cor_dir = options["sen2cor_path"]
    input_file = options["input_file"]
    output_dir = options["output_dir"]
    nprocs = int(options["nprocs"])

    if not os.path.isdir(sen2cor_dir):
        grass.fatal(_(f"Directory {sen2cor_dir} does not exist."))

    # test if sen2cor is installed properly
    l2a_process = os.path.join(sen2cor_dir, "bin", "L2A_Process")
    cmd = grass.Popen(
        f"{l2a_process} --help",
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    resp = cmd.communicate()
    if resp[1] != b"":
        grass.fatal(_("Sen2Cor is not installed properly."))

    # test nprocs settings
    if nprocs > mp.cpu_count():
        grass.fatal(
            f"Using {nprocs} parallel processes but only "
            f"{mp.cpu_count()} CPUs available."
        )
    elif nprocs == -2:
        nprocs = mp.cpu_count() - 1

    # test input data
    if not os.path.isdir(input_file):
        grass.fatal(_(f"Input file {input_file} not found"))
    elif not input_file.endswith(".SAFE"):
        grass.fatal(_("Input file is not in .SAFE format"))

    # find L2A_GIPP.xml, it can be in different folders depending on version
    for root, dir, files in os.walk(sen2cor_dir):
        if "L2A_GIPP.xml" in files:
            gipp_path = os.path.join(root, "L2A_GIPP.xml")

    if not gipp_path:
        grass.fatal(_(f"Could not find L2A_GIPP.xml in {sen2cor_dir}"))

    # modify L2A_GIPP.xml according to user input
    gipp_modified = grass.tempfile()
    rm_files.append(gipp_modified)
    tree = ET.parse(gipp_path)
    root = tree.getroot()
    rel_dem_dir = f"srtm_{os.getpid()}"
    # DEM list: https://github.com/senbox-org/snap-engine/blob/c92e2506eb57d56f6c7d3e739822f73c8186524c/etc/snap.auxdata.properties#L28
    # - CGIAR-SRTM-1sec = ~90m resolution (0:00:03 deg):
    update_dict = {
        "Nr_Threads": options["nprocs"],
        "DEM_Directory": f"dem/{rel_dem_dir}",
        "DEM_Reference": (
            "https://srtm.csi.cgiar.org/wp-content"
            "/uploads/files/srtm_5x5/TIFF/"
        ),
        "Aerosol_Type": options["aerosol_type"].upper(),
        "Mid_Latitude": options["season"].upper(),
        "Ozone_Content": options["ozone_content"],
        "WV_Correction": "1",
        "VIS_Update_Mode": "1",
        "WV_Watermask": "1",
        "Cirrus_Correction": "TRUE",
        "DEM_Terrain_Correction": "TRUE",
        # BRDF Correction is buggy in sen2cor, hence deactivated
        "BRDF_Correction": "0",
        "Downsample_20_to_60": "FALSE",
    }
    for item in update_dict.items():
        for elem in root.iter(item[0]):
            elem.text = item[1]
    tree._setroot(root)
    tree.write(gipp_modified, encoding="utf-8", xml_declaration=True)

    # build sen2cor command
    cmd_str = (
        f"{l2a_process} --GIP_L2A {gipp_modified} "
        f"--output_dir {output_dir} {input_file}"
    )
    sen2cor_cmd = grass.Popen(
        cmd_str, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    grass.message(_(f"Running sen2cor using command:\n{cmd_str}\n..."))
    sen2cor_resp = sen2cor_cmd.communicate()
    successful = False
    if "terminated successfully" in sen2cor_resp[0].decode("utf-8"):
        successful = True

    input_file_dateblock = os.path.basename(input_file).split("_")[2]
    # name of output file is not known before
    for file in os.listdir(output_dir):
        try:
            output_file_dateblock = file.split("_")[2]
            if output_file_dateblock == input_file_dateblock:
                if successful is True:
                    grass.message(
                        _(
                            "Atmospherical Correction complete, generated "
                            f"output file <{os.path.join(output_dir, file)}>"
                        )
                    )

                else:
                    # remove result if not successful
                    rm_folders.append(os.path.join(output_dir, file))
        except Exception:
            pass

    if successful is False:
        error_msg = ""
        for sen2cor_r in sen2cor_resp:
            error_msg += sen2cor_r.decode("utf-8")
        grass.fatal(_(f"Error using sen2cor: {error_msg}"))

    if flags["r"]:
        rm_folders.append(input_file)


if __name__ == "__main__":
    options, flags = grass.parser()
    atexit.register(cleanup)
    main()
