"""
Name:       i.sentinel_2.autotraining test
Purpose:    Tests i.sentinel_2.autotraining using actinia-test-assets.
Author:     Guido Riembauer
Copyright:  (C) 2021 Guido Riembauer, mundialis, and the GRASS
            Development Team
Licence:    This program is free software under the GNU General Public
            License (>=v2). Read the file COPYING that comes with GRASS
            for details.
"""
import os

from grass.gunittest.case import TestCase
from grass.gunittest.main import test
from grass.gunittest.gmodules import SimpleModule
import grass.script as grass


class TestISentinelAutotraining(TestCase):
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
    old_region = "saved_region_{}".format(pid_str)
    # calculated from the nc_spm dataset:
    ndvi = "ndvi_{}".format(pid_str)
    ndwi = "ndwi_{}".format(pid_str)
    ndbi = "ndbi_{}".format(pid_str)
    bsi = "bsi_{}".format(pid_str)
    # to be generated
    str_column = "class_string"
    int_column = "class_int"
    tr_map_rast = "tr_map_rast_{}".format(pid_str)
    tr_map_vect = "tr_map_vect_{}".format(pid_str)

    @classmethod
    def setUpClass(self):
        """Ensures expected computational region and generated data"""
        grass.run_command("g.region", save=self.old_region)
        grass.run_command("g.region", raster=self.blue)
        # calculate indices
        ndvi_exp = (
            f"{self.ndvi} = float({self.nir}-{self.red}/"
            f"float({self.nir}+{self.red}))"
        )
        ndwi_exp = (
            f"{self.ndwi} = float({self.green}-{self.nir})/"
            f"float({self.green}+{self.nir})"
        )
        ndbi_exp = (
            f"{self.ndbi} = float({self.swir}-{self.nir})/"
            f"float({self.swir}+{self.nir})"
        )
        bsi_exp = (
            f"{self.bsi} = float(({self.swir}+{self.red})-"
            f"({self.nir}+{self.blue}))/float(({self.swir}+"
            f"{self.blue})+({self.nir}+{self.blue}))"
        )
        for exp in [ndvi_exp, ndwi_exp, ndbi_exp, bsi_exp]:
            grass.run_command("r.mapcalc", expression=exp)

    @classmethod
    def tearDownClass(self):
        """Remove the temporary region and generated data"""
        grass.run_command("g.region", region=self.old_region)
        for rast in [self.ndvi, self.ndwi, self.ndbi, self.bsi]:
            grass.run_command("g.remove", type="raster", name=rast, flags="f")

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
                ("Column {} is not in the output" "vector map").format(col),
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
