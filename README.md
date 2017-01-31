BiobOx provides a collection of data structures and methods for loading, manipulating and analyzing atomistic and pseudoatomistic structures.

BiobOx main features:
* importing of PDB, PQR and GRO files, possibly containing multiple conformations (e.g. multi PDB, gro trajectory)
* generation of coarse grain shapes composed of specific arrangements of pseudoatoms
* loading and manipulation of density maps, including their transformation into a solid object upon isovalue definition
* assemblies of any points arrangement can be produced (i.e. densities converted in solid and geometric shapes can be equally treated).

Allowed operations on structures incude:
* rototranslation and alignment on principal axes
* on ensembles: RMSD, RMSF, PCA and clustering
* calculation of CCS, SAXS, SASA, convex hull, s2 (for molecules), mass and volume estimation
* atomselect for molecules and assemblies of molecules
* shortest physical paths between atoms on molecule using Theta* (or A*)
* density map simulation


## INSTALLATION AND REQUIREMENTS

BiobOx requires Python2.7 and the following packages:
* numpy
* scipy
* scikit-klearn
* cython
* pandas

install with: `python setup.py install`

Optional external software:
* CCS calculation relies on a call to IMPACT (requires IMPACTPATH environment variable)
* SAXS simulations rely on a call to crysol, from ATSAS suite (requires ATSASPATH environment variable)


## CREDITS

author: Matteo Degiacomi (matteo.degiacomi[at]gmail.com)

other contributions:
* Importing of MRC format maps adapted from [CHIMERA](https://www.cgl.ucsf.edu/chimera/)
* Kabsch algorithm for RMSD calculation from [Pymol](https://www.pymol.org/)
* A* implementation from * [redblobgames](http://www.redblobgames.com)


## KNOWN ISSUES
* SASA values are underestimated