#!/usr/bin/env python3
#
############################################################################
#
# MODULE:      i.sentinel_2.autotraining test
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

import os

from grass.gunittest.case import TestCase
from grass.gunittest.main import test
from grass.gunittest.gmodules import SimpleModule
import grass.script as grass


class TestISentinel2Autotraining(TestCase):
    """Test class for i.sentinel_2.autotraining"""

    pid_str = str(os.getpid())
    # from actinia_test assets:
    probav_class = "probav_classification_2019"
    probav_treecov = "probav_treecoverfraction_2019"
    gong_lc_map = "gong_lc"
    ghs_built_map = "ghs_built"
    tr_map_rast_ref = "tr_map_rast_ref"
    # from the nc_spm dataset:
    blue = "lsat7_2002_10"
    green = "lsat7_2002_20"
    red = "lsat7_2002_30"
    nir = "lsat7_2002_40"
    swir = "lsat7_2002_50"
    old_region = f"saved_region_{pid_str}"
    # calculated from the nc_spm dataset:
    ndvi = f"ndvi_{pid_str}"
    ndwi = f"ndwi_{pid_str}"
    ndbi = f"ndbi_{pid_str}"
    bsi = f"bsi_{pid_str}"
    # to be generated
    str_column = "class_string"
    int_column = "class_int"
    tr_map_rast = f"tr_map_rast_{pid_str}"
    tr_map_vect = f"tr_map_vect_{pid_str}"

    @classmethod
    # pylint: disable=invalid-name
    def setUpClass(cls):
        """Ensures expected computational region and generated data"""
        grass.run_command("g.region", save=cls.old_region)
        grass.run_command("g.region", raster=cls.blue)
        # calculate indices
        ndvi_exp = (
            f"{cls.ndvi} = float({cls.nir}-{cls.red}/"
            f"float({cls.nir}+{cls.red}))"
        )
        ndwi_exp = (
            f"{cls.ndwi} = float({cls.green}-{cls.nir})/"
            f"float({cls.green}+{cls.nir})"
        )
        ndbi_exp = (
            f"{cls.ndbi} = float({cls.swir}-{cls.nir})/"
            f"float({cls.swir}+{cls.nir})"
        )
        bsi_exp = (
            f"{cls.bsi} = float(({cls.swir}+{cls.red})-"
            f"({cls.nir}+{cls.blue}))/float(({cls.swir}+"
            f"{cls.blue})+({cls.nir}+{cls.blue}))"
        )
        for exp in [ndvi_exp, ndwi_exp, ndbi_exp, bsi_exp]:
            grass.run_command("r.mapcalc", expression=exp)

    @classmethod
    # pylint: disable=invalid-name
    def tearDownClass(cls):
        """Remove the temporary region and generated data"""
        grass.run_command("g.region", region=cls.old_region)
        for rast in [cls.ndvi, cls.ndwi, cls.ndbi, cls.bsi]:
            grass.run_command("g.remove", type="raster", name=rast, flags="f")

    # pylint: disable=invalid-name
    def tearDown(self):
        """Remove the outputs created
        This is executed after each test run.
        """
        grass.run_command(
            "g.remove", type="raster", name=self.tr_map_rast, flags="f"
        )
        grass.run_command(
            "g.remove", type="vector", name=self.tr_map_vect, flags="f"
        )

    def test_autotraining_vector(self):
        """Test if the vector result of i.sentinel_2.autotraining
        is valid"""
        auto_tr = SimpleModule(
            "i.sentinel_2.autotraining",
            ndvi=self.ndvi,
            ndwi=self.ndwi,
            ndbi=self.ndbi,
            bsi=self.bsi,
            ref_classification_probav=self.probav_class,
            ref_treecover_fraction_probav=self.probav_treecov,
            ref_classification_gong=self.gong_lc_map,
            ref_ghs_built=self.ghs_built_map,
            output_vector=self.tr_map_vect,
            output_raster=self.tr_map_rast,
            str_column=self.str_column,
            int_column=self.int_column,
            npoints=1000,
            percentage_threshold=0.01,
        )
        self.assertModule(auto_tr)
        self.assertVectorExists(self.tr_map_vect)
        # check there are 4000 entries in the vector
        vinfo = grass.parse_command("v.info", map=self.tr_map_vect, flags="tg")
        self.assertEqual(
            vinfo["points"],
            "4000",
            ("The number of generated" " points is not 4000."),
        )
        vinfo_cols = list(
            grass.parse_command(
                "v.info", map=self.tr_map_vect, flags="c"
            ).keys()
        )
        for col in ["INTEGER|class_int", "CHARACTER|class_string"]:
            self.assertIn(
                col,
                vinfo_cols,
                f"Column {col} is not in the output" "vector map",
            )

    def test_autotraining_raster(self):
        """Test if the raster result of i.sentinel_2.autotraining
        is equal to the reference
        """
        auto_tr = SimpleModule(
            "i.sentinel_2.autotraining",
            ndvi=self.ndvi,
            ndwi=self.ndwi,
            ndbi=self.ndbi,
            bsi=self.bsi,
            ref_classification_probav=self.probav_class,
            ref_treecover_fraction_probav=self.probav_treecov,
            ref_classification_gong=self.gong_lc_map,
            ref_ghs_built=self.ghs_built_map,
            output_vector=self.tr_map_vect,
            output_raster=self.tr_map_rast,
            str_column=self.str_column,
            int_column=self.int_column,
            npoints=1000,
            percentage_threshold=0.01,
        )
        self.assertModule(auto_tr)
        self.assertRasterExists(self.tr_map_rast)
        # assert the raster is equal to the reference
        self.assertRastersNoDifference(
            self.tr_map_rast, self.tr_map_rast_ref, precision=0.0
        )


if __name__ == "__main__":
    test()
