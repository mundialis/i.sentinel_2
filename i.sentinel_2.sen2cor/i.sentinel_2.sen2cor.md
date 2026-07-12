## DESCRIPTION

*i.sentinel_2.sen2cor* runs atmospherical correction on a single
Sentinel-2 Level-1C scene using
[Sen2Cor](http://step.esa.int/main/snap-supported-plugins/sen2cor/).
Therefore, Sen2Cor needs to be installed and configured to use from the
command line (it is recommended to use the standalone command line
tool).

The entire processing takes place outside of GRASS GIS. This addon is
helpful when used as an intermediate step between downloading
([i.sentinel.download](i.sentinel.download.md)) and importing
([i.sentinel.import](i.sentinel.import.md)) of L1C (then L2A) data.

Most of the Sen2Cor parameters are not changed by this addon in order to
make the results consistent with ESA's L2A standard products. Options
from the configurable Sen2Cor parameters supported by this addon can be
adapted by the user according to [Level 2A Input Output Data
Definition](http://step.esa.int/thirdparties/sen2cor/2.8.0/docs/S2-PDGS-MPC-L2A-IODD-V2.8.pdf).

## EXAMPLE

```sh
i.sentinel_2.sen2cor input_file=S2A_MSIL1C_20190606T102031_N0207_R065_T33UUA_20190606T123501.SAFE output_dir=tmp/sen2cor_output sen2cor_path=/home/user/sen2cor
```

## SEE ALSO

*[i.sentinel.download](i.sentinel.download.md),
[i.sentinel.import](i.sentinel.import.md)*

## REQUIREMENTS

[Sen2Cor](http://step.esa.int/main/snap-supported-plugins/sen2cor/)
needs to be installed and configured for use from the command line. For
additional information, see:

- [Sen2Cor Release
  Note](https://step.esa.int/thirdparties/sen2cor/2.11.0/docs/OMPC.TPZG.SRN.003---i1r0---Sen2Cor-2.11.00-Software-Release-Note.pdf)
- [Sen2Cor Configuration and User
  Manual](https://step.esa.int/thirdparties/sen2cor/2.11.0/docs/OMPC.TPZG.SUM.001---i1r0---Sen2Cor-2.11.00-Configuration-and-User-Manual.pdf)
- [Level 2A Input Output Data
  Definition](https://step.esa.int/thirdparties/sen2cor/2.11.0/docs/OMPC.TPZG.IOD.001---i1r0---Sen2Cor-2.11.00-IODD.pdf)

## AUTHOR

Guido Riembauer, [mundialis GmbH & Co. KG](https://www.mundialis.de/),
Germany
