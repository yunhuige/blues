# `BLUES`: Binding modes of Ligands Using Enhanced Sampling
<img align="right" src="./images/blues.png" width="300">

This package takes advantage of non-equilibrium candidate Monte Carlo moves (NCMC) to help sample between different ligand binding modes.

Latest release:
[![Build Status](https://travis-ci.org/MobleyLab/blues.svg?branch=master)](https://travis-ci.org/MobleyLab/blues)
[![Documentation Status](https://readthedocs.org/projects/mobleylab-blues/badge/?version=stable)](https://mobleylab-blues.readthedocs.io/en/stable/?badge=stable)
[![codecov](https://codecov.io/gh/MobleyLab/blues/branch/master/graph/badge.svg)](https://codecov.io/gh/MobleyLab/blues)
[![Anaconda-Server Badge](https://anaconda.org/mobleylab/blues/badges/version.svg)](https://anaconda.org/mobleylab/blues)
 [![DOI](https://zenodo.org/badge/62096511.svg)](https://zenodo.org/badge/latestdoi/62096511)

## Citations
#### Publication
- [Gill, S; Lim, N. M.; Grinaway, P.; Rustenburg, A. S.; Fass, J.; Ross, G.; Chodera, J. D.; Mobley, D. L. “Binding Modes of Ligands Using Enhanced Sampling (BLUES): Rapid Decorrelation of Ligand Binding Modes Using Nonequilibrium Candidate Monte Carlo”](https://pubs.acs.org/doi/abs/10.1021/acs.jpcb.7b11820) - Journal of Physical Chemistry B. February 27, 2018

#### Preprints
- [BLUES v1](https://chemrxiv.org/articles/Binding_Modes_of_Ligands_Using_Enhanced_Sampling_BLUES_Rapid_Decorrelation_of_Ligand_Binding_Modes_Using_Nonequilibrium_Candidate_Monte_Carlo/5406907) - ChemRxiv September 19, 2017
- [BLUES v2](https://doi.org/10.26434/chemrxiv.5406907.v2) - ChemRxiv September 25, 2017

## Manifest
* `blues/` -  Source code and example scripts for BLUES toolkit
* `devdocs/` - Class diagrams for developers
* `devtools/` - Developer tools and documentation for conda, travis, and issuing a release
* `images/` - Images/logo for repository
* `notebooks` - Jupyter notebooks for testing/development

## Prerequisites
BLUES is compatible with MacOSX/Linux with Python=3.6.

Install [miniconda](http://conda.pydata.org/miniconda.html) according to your system.


## Installation
[ReadTheDocs: Installation](https://mobleylab-blues.readthedocs.io/en/latest/installation.html)

Recommended: Install releases from conda

```bash
# Create a clean environment (python 3.6 is required)
conda create -n blues python=3.6
conda activate blues

# Install OpenEye toolkits and related tools first
conda install -c openeye/label/Orion -c omnia oeommtools
conda install -c openeye openeye-toolkits

# Install necessary dependencies
conda install -c omnia -c conda-forge openmmtools=0.15.0 openmm=7.4.2 numpy cython

conda install -c mobleylab blues
```

Install from source (if conda installation fails)
```bash
# Clone the BLUES repository
git clone https://github.com/MobleyLab/blues.git ./blues

# Install some dependencies
conda install -c omnia -c conda-forge openmmtools=0.15.0 openmm=7.4.2 numpy cython

# To use SideChainMove class, OpenEye toolkits and related tools are requried (requires OpenEye License)
conda install -c openeye/label/Orion -c omnia oeommtools
conda install -c openeye openeye-toolkits

# Install BLUES package from the top directory
pip install -e .

# To validate your BLUES installation run the tests (need pytest)
cd blues/tests
pytest -v -s
```

## Documentation
For documentation on the BLUES modules see [ReadTheDocs: Modules](https://mobleylab-blues.readthedocs.io/en/latest/module_doc.html)
For a tutorial on how to use BLUES see [ReadTheDocs: Tutorial](https://mobleylab-blues.readthedocs.io/en/latest/tutorial.html)

### BLUES using NCMC
This package takes advantage of non-equilibrium candidate Monte Carlo moves (NCMC) to help sample between different ligand binding modes using the OpenMM simulation package.  One goal for this package is to allow for easy additions of other moves of interest, which will be covered below.

### Example Use
An example of how to set up a simulation sampling the binding modes of toluene bound to T4 lysozyme using NCMC and a rotational move can be found in `examples/example_rotmove.py`

### Actually using BLUES
The integrator of `BLUES` contains the framework necessary for NCMC.  Specifically, the integrator class calculates the work done during a NCMC move. It also controls the lambda scaling of parameters. The integrator that BLUES uses inherits from `openmmtools.integrators.AlchemicalNonequilibriumLangevinIntegrator` to keep track of the work done outside integration steps, allowing Monte Carlo (MC) moves to be incorporated together with the NCMC thermodynamic perturbation protocol. Currently the `openmmtools.alchemy` package is used to generate the lambda parameters for the ligand, allowing alchemical modification of the sterics and electrostatics of the system.
The `Simulation` class in `blues/simulation.py` serves as a wrapper for running NCMC simulations.

### Implementing Custom Moves
Users can implement their own MC moves into NCMC by inheriting from an appropriate `blues.moves.Move` class and constructing a custom `move()` method that only takes in an Openmm context object as a parameter. The `move()` method will then access the positions of that context, change those positions, then update the positions of that context. For example if you would like to add a move that randomly translates a set of coordinates the code would look similar to this pseudocode:

```python
from blues.moves import Move
class TranslationMove(Move):
   	def __init__(self, atom_indices):
   		self.atom_indices = atom_indices
   	def move(context):
   	"""pseudocode for move"""
   		positions = context.context.getState(getPositions=True).getPositions(asNumpy=True)
   		#get positions from context
   		#use some function that translates atom_indices
   		newPositions = RandomTranslation(positions[self.atom_indices])
   		context.setPositions(newPositions)
   		return context
```

### Combining Moves
**Note: This feature has not been tested, use at your own risk.**
If you're interested in combining moves together sequentially–say you'd like to perform a rotation and translation move together–instead of coding up a new `Move` class that performs that, you can instead leverage the functionality of existing `Move`s using the `CombinationMove` class. `CombinationMove` takes in a list of instantiated `Move` objects. The `CombinationMove`'s `move()` method perfroms the moves in either listed or reverse order. Replicating a rotation and translation move on t, then, can effectively be done by passing in an instantiated TranslationMove (from the pseudocode example above) and RandomLigandRotation.
One important non-obvious thing to note about the CombinationMove class is that to ensure detailed balance is maintained, moves are done half the time in listed order and half the time in the reverse order.

## Versions:
- Version 0.0.1: Basic BLUES functionality/package
- [Version 0.0.2](http://dx.doi.org/10.5281/zenodo.438714): Maintenance release fixing a critical bug and improving organization as a package.
- [Version 0.0.3](http://dx.doi.org/10.5281/zenodo.569065): Refactored BLUES functionality and design.
- [Version 0.0.4](http://dx.doi.org/10.5281/zenodo.569074): Minor bug fixes plus a functionality problem on some GPU configs.
- [Version 0.1.0](http://dx.doi.org/10.5281/zenodo.837900): Refactored move proposals, added Monte Carlo functionality, Smart Darting moves, and changed alchemical integrator.
- [Version 0.1.1](https://doi.org/10.5281/zenodo.1028925): Features to boost move acceptance such as freezing atoms in the NCMC simulation and adding extra propagation steps in the alchemical integrator.
- [Version 0.1.2](https://doi.org/10.5281/zenodo.1040364): Incorporation of SideChainMove functionality (Contributor: Kalistyn Burley)
- [Version 0.1.3](https://doi.org/10.5281/zenodo.1048250): Improvements to simulation logging functionality and parameters for extra propagation.
- [Version 0.2.0](https://doi.org/10.5281/zenodo.1284568): YAML support, API changes, custom reporters.
- [Version 0.2.1](https://doi.org/10.5281/zenodo.1288925): Bug fix in alchemical correction term
- [Version 0.2.2](https://doi.org/10.5281/zenodo.1324415): Bug fixes for OpenEye tests and restarting from the YAML; enhancements to the Logger and package installation.
- [Version 0.2.3](https://zenodo.org/badge/latestdoi/62096511): Improvements to Travis CI, fix in velocity synicng, and add tests for checking freezing selection.
- [Version 0.2.4](https://doi.org/10.5281/zenodo.2672932): Added a simple test system (charged ethylene) which can run quickly on CPU.
- [Version 0.2.5](https://doi.org/10.5281/zenodo.4118606): This contains numerous small changes/fixes since the v0.2.4 release, but most notably includes the introduction of water hopping as described at https://doi.org/10.26434/chemrxiv.12429464.v1

## Acknowledgements
We would like to thank Patrick Grinaway and John Chodera for their basic code framework for NCMC in OpenMM (see https://github.com/choderalab/perses/tree/master/perses/annihilation), and John Chodera and Christopher Bayly for their helpful discussions.
