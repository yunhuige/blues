from simtk.openmm.app import *
from simtk.openmm import *
from ncmc_switching import *
import simtk.unit as unit
import mdtraj as md
import math
from alchemy import AbsoluteAlchemicalFactory, AlchemicalState
import numpy as np
from openmmtools import testsystems
from storage import NetCDFStorageView



def get_lig_residues(lig_resname, coord_file, top_file=None):
    """
    This controls the ability to run a ncmc simulation with MD

    Arguments
    ---------
    lig_resname: str, resname that you want to get the atom indicies for (ex. 'LIG')
    coord_file:  file, cooridnate file (.pdb, .gro, .h5 etc)
    top_file: file, if topology isn't innately included in coordinates, include topology here

    Returns
    -------
    rotation : nx3 np.array in units.nm
        positions of ligand after random rotation

    """

    if top_file == None:
        traj = md.load(coord_file)
    else:
        traj = md.load(coord_file, top=top_file)

    lig_atoms = traj.top.select(("resname =~ %s") % lig_resname)
    first_res = min(lig_atoms)
    last_res = max(lig_atoms)
    return first_res, last_res, lig_atoms

def quantity_is_finite(quantity):
    """
    Check that elements in quantity are all finite.
    Parameters
    ----------
    quantity : simtk.unit.Quantity
        The quantity to check
    Returns
    -------
    is_finite : bool
        If quantity is finite, returns True; otherwise False.
    """
    if np.any( np.isnan( np.array(quantity / quantity.unit) ) ):
        return False
    return True


class md_reporter:
    """
    class to handle error reporting
    """

    def __init__(self):
        self.traj = None
        self.shape = None
        self.temp_traj = None
        self.first = 0
        self.last  = -1

    def initialize(self, nc_context):

        nc_stateinfo = nc_context.getState(True, False, False, False, False, True)
        tempPos = nc_stateinfo.getPositions(asNumpy=True)

        last_x, last_y = np.shape(tempPos)
        self.shape = (np.reshape(tempPos, (1, last_x, last_y))).value_in_unit(unit.nanometers)

    def add_frame(self, nc_context):
        if self.traj == None:
            nc_stateinfo = nc_context.getState(True, False, False, False, False, True)
            tempPos = nc_stateinfo.getPositions(asNumpy=True)

            last_x, last_y = np.shape(tempPos)
            self.traj = (np.reshape(tempPos, (1, last_x, last_y))).value_in_unit(unit.nanometers)
        else:
            nc_stateinfo = nc_context.getState(True, False, False, False, False, True)
            tempPos = nc_stateinfo.getPositions(asNumpy=True)

            last_x, last_y = np.shape(tempPos)
            temp = (np.reshape(tempPos, (1, last_x, last_y))).value_in_unit(unit.nanometers)
            self.traj = np.concatenate((self.traj, temp))
    def add_temp_traj(self, nc_context):
        if self.temp_traj == None:
            nc_stateinfo = nc_context.getState(True, False, False, False, False, True)
            tempPos = nc_stateinfo.getPositions(asNumpy=True)

            last_x, last_y = np.shape(tempPos)
            self.temp_traj = (np.reshape(tempPos, (1, last_x, last_y))).value_in_unit(unit.nanometers)
        else:
            nc_stateinfo = nc_context.getState(True, False, False, False, False, True)
            tempPos = nc_stateinfo.getPositions(asNumpy=True)

            last_x, last_y = np.shape(tempPos)
            temp = (np.reshape(tempPos, (1, last_x, last_y))).value_in_unit(unit.nanometers)
            if True not in np.isnan(temp):
                self.temp_traj = np.concatenate((self.temp_traj, temp))
    def combine_traj(self):
        if self.traj != None and self.temp_traj != None:
            if True not in np.isnan(self.temp_traj):
                self.traj = np.concatenate((self.traj, self.temp_traj))
            self.temp_traj = None
        if self.traj == None and self.temp_traj != None:
            self.traj = self.temp_traj[:]

    def save_traj(self, output_name, topology, traj=None):
        if traj == None:
            traj = self.traj
        last_top = md.Topology.from_openmm(topology)
        broken_ncmc = md.Trajectory(xyz=traj, topology=last_top)
        try:
            broken_ncmc.save_dcd(output_name)
        except ValueError:
            print('couldnt output', output_name, 'values too large')

         
def rand_rotation_matrix():
    rand_quat = md.utils.uniform_quaternion()
    matrix_out = md.utils.rotation_matrix_from_quaternion(rand_quat)
    return matrix_out

def zero_masses( system, firstres, lastres):
    for index in range(firstres, lastres):
        system.setParticleMass(index, 0*unit.daltons)

def selectres(reslist, inpcrd, prmtop):
    t = md.load(inpcrd, top=prmtop)
    output_list = []
    for entry in reslist:
        output_list.extend(t.top.select(("resid %s") % (entry)))
    return output_list

def zero_allother_masses( system, indexlist):
    num_atoms = system.getNumParticles()
    for index in range(num_atoms):
        if index in indexlist:
            pass
        else:
            system.setParticleMass(index, 0*unit.daltons)


class SimNCMC(object):
    def __init__(self, temperature, residueList, storage=None, write_ncmc_interval=None, **kwds):
        """
        This controls the ability to run a ncmc simulation with MD

        Arguments
        ---------
        md_simulation: a Simulation object containing the system of interest
        nc_context:  openmm.context
        nc_integrator: nc integrator
        nstepsNC: int, number of steps of NC to perform
        nstepsMD: int, number of steps of nstepsMD to perform
        niter:    int, number of iterations of NC/MD to perform in total
        """
        super().__init__(**kwds)
        print('testing1')

        self.total_mass = 0
        self.mass_list = None
        self.residueList = residueList
        self.acceptance = 0
        self.md_simulation = None
        self.dummy_simulation = None
        self.nc_context = None
        self.nc_integrator = None
        self.nc_pos = None
        self._storage = None

        kB = unit.BOLTZMANN_CONSTANT_kB * unit.AVOGADRO_CONSTANT_NA
        kT = kB * temperature
        beta = 1.0 / kT
        self.beta = beta
        if storage is not None:
            self._storage = NetCDFStorageView(storage, modname=self.__class__.__name__)
        self.write_ncmc_interval = write_ncmc_interval



    def set_res(self, residueList):
        self.residueList = residueList

    def get_particle_masses(self, system, residueList=None):
        if residueList == None:
            residueList = self.residueList
        mass_list = []
        total_mass = 0*unit.dalton
        for index in residueList:
            mass = system.getParticleMass(index)
            total_mass = total_mass + mass
            print('mass', mass, 'total_mass', total_mass)
            mass_list.append([mass])
        total_mass = np.sum(mass_list)
        mass_list = np.asarray(mass_list)
        mass_list.reshape((-1,1))
        total_mass = np.array(total_mass)
        total_mass = np.sum(mass_list)
        temp_list = np.zeros((len(residueList), 1))
        for index in range(len(residueList)):
            mass_list[index] = (np.sum(mass_list[index])).value_in_unit(unit.daltons)
        mass_list =  mass_list*unit.daltons
        self.total_mass = total_mass
        self.mass_list = mass_list
        return total_mass, mass_list
            
    def zero_masses(self, system, atomList=None):
        for index in (atomList):
            system.setParticleMass(index, 0*unit.daltons)
        

    def calculate_com(self, total_mass, mass_list, pos_state, residueList=None, rotate=True):
        """
        This function calculates the com of specified residues and optionally rotates them around the center of mass

        Arguments
        ---------
        total_mass: simtk.unit.quantity.Quantity in units daltons, contains the total masses of the particles for COM calculation
        mass_list:  nx1 np.array in units daltons, contains the masses of the particles for COM calculation
        pos_state:  nx3 np. array in units.nanometers, returned from state.getPositions
        residueList: list of int, index of atoms which you'll calculate the total com for 
        rotate: boolean, if True, rotates center of mass by random rotation matrix
        Returns
        -------
        rotation : nx3 np.array in units.nm
            positions of ligand after random rotation

        """
        if residueList == None:
            residueList = self.residueList
        if mass_list == None:
            mass_list = self.mass_list
        if total_mass == None:
            total_mass = self.total_mass
        if mass_list == None:
            mass_list = self.mass_list

        #choose ligand indicies
        copy_orig = copy.deepcopy(pos_state)
        lig_coord = np.zeros((len(residueList), 3))
        for index, resnum in enumerate(residueList):
            lig_coord[index] = copy_orig[resnum]
        lig_coord = lig_coord*unit.nanometers
        copy_coord = copy.deepcopy(lig_coord)
        #mass corrected coordinates (to find COM)
#        print('mass_list', mass_list)
#        print('total_mass', total_mass)
#        print('copy_coord', copy_coord)
        mass_corrected = mass_list / total_mass * copy_coord
        sum_coord = mass_corrected.sum(axis=0).value_in_unit(unit.nanometers)
        com_coord = [0.0, 0.0, 0.0]*unit.nanometers
        #units are funky, so do this step to get them to behave right
        for index in range(3):
            com_coord[index] = sum_coord[index]*unit.nanometers
        if rotate ==True:
            for index in range(3):
                lig_coord[:,index] = lig_coord[:,index] - com_coord[index]
            #multiply lig coordinates by rot matrix and add back COM translation from origin
            rotation =  np.dot(lig_coord.value_in_unit(unit.nanometers), rand_rotation_matrix())*unit.nanometers
            rotation = rotation + com_coord
            return rotation
        else:    
        #remove COM from ligand coordinates to then perform rotation
            return com_coord            #remove COM from ligand coordinates to then perform rotation

    def create_alchemicalSystem(self, coord_file, top_file, residueList=None):
        if residueList == None:
            residueList = self.residueList
        prmtop = openmm.app.AmberPrmtopFile(top_file)
        inpcrd = openmm.app.AmberInpcrdFile(coord_file)
        temp_system = prmtop.createSystem(nonbondedMethod=openmm.app.PME, nonbondedCutoff=1*unit.nanometer, constraints=openmm.app.HBonds)
        testsystem = testsystems.TestSystem
        testsystem.system = temp_system
        testsystem.topology = prmtop.topology
        testsystem.positions = inpcrd.positions
        firstres, lastres, ligand_atoms = get_lig_residues(lig_resname='LIG', coord_file=coord_file, top_file=top_file)
        factory = AbsoluteAlchemicalFactory(testsystem.system, ligand_atoms=ligand_atoms, annihilate_sterics=True, annihilate_electrostatics=True)
        self.alchemical_system = factory.createPerturbedSystem()
        return self.alchemical_system

    def create_normalSystem(self, coord_file, top_file):
        prmtop = openmm.app.AmberPrmtopFile(top_file)
        inpcrd = openmm.app.AmberInpcrdFile(coord_file)
        temp_system = prmtop.createSystem(nonbondedMethod=openmm.app.PME, nonbondedCutoff=1*unit.nanometer, constraints=openmm.app.HBonds)
        testsystem = testsystems.TestSystem
        testsystem.system = temp_system 
        testsystem.topology = prmtop.topology
        testsystem.positions = inpcrd.positions
        self.normalsystem = testsystem
        return self.normalsystem

    def createNormalSimulation(self, friction=1/unit.picosecond, timestep=0.002*unit.picoseconds, temperature=None):
        if temperature == None:
            temperature = self.temperature
        self.md_integrator = openmm.openmm.LangevinIntegrator(temperature, friction, timestep)
        self.dummy_integrator = openmm.openmm.LangevinIntegrator(temperature, friction, timestep)
        self.md_simulation = openmm.app.simulation.Simulation(topology=self.normalsystem.topology, system=self.normalsystem.system, integrator=self.md_integrator)
        self.dummy_simulation = openmm.app.simulation.Simulation(topology=self.normalsystem.topology, system=self.normalsystem.system, integrator=self.dummy_integrator)
   
    def createAlchemicalContext(self, alchemical_system=None):
        if alchemical_system == None:
            alchemcial_system = self.alchemical_system
        self.nc_context = openmm.Context(alchemical_system)

    def rotationalMove(self, context=None, residueList=None):
        if residueList == None:
            residueList = self.residueList
        rot_output = self.calculate_com(total_mass=self.total_mass, mass_list=self.mass_list, pos_state=self.nc_pos, residueList=residueList)
        rot_output = rot_output[:].value_in_unit(unit.nanometers)
        rotPos = self.nc_pos.value_in_unit(unit.nanometers)
        for index, resnum in enumerate(residueList):
            rotPos[resnum] = rot_output[index]
        rotPos[:] = rotPos*unit.nanometers
        self.nc_context.setPositions(rotPos)









    def testintegrator(self, md_simulation, nc_context, nc_integrator, dummy_simulation, movekey=None, nstepsNC=25, nstepsMD=1000, niter=10, periodic=True, verbose=False, residueList=None, alchemical_correction=False, rot_report=False, ncmc_report=False, origPos=None):
        if residueList == None:
            residueList = self.residueList
        self.md_simulation = md_simulation
        self.dummy_simulation = dummy_simulation
        self.nc_context = nc_context
        self.nc_integrator = nc_integrator
        #set up initial counters/ inputs
        accCounter = 0
        otherCounter = 0
        nc_stateinfo = nc_context.getState(True, False, False, False, False, periodic)
        tempPos = nc_stateinfo.getPositions(asNumpy=True)

        last_x, last_y = np.shape(tempPos)
        ncmc_frame = (np.reshape(tempPos, (1, last_x, last_y))).value_in_unit(unit.nanometers)
        tempTraj = np.array(())
        if rot_report == True:
            rot_reporter = md_reporter()
        if ncmc_report == True:
            ncmc_reporter = md_reporter()


        #set inital conditions
        md_stateinfo = md_simulation.context.getState(True, True, False, True, True, periodic)
        oldPos = md_stateinfo.getPositions(asNumpy=True)
        oldVel = md_stateinfo.getVelocities(asNumpy=True)

        oldPE =  md_stateinfo.getPotentialEnergy()
        oldKE =  md_stateinfo.getKineticEnergy()
        nc_context.setPositions(oldPos)
        self.nc_pos = oldPos
        nc_context.setVelocities(oldVel)
        #TODO
        
        first_ncmc = (np.reshape(tempPos, (1, last_x, last_y))).value_in_unit(unit.nanometers)




        for stepsdone in range(niter):
            print('performing ncmc step')
            print('accCounter =', accCounter)
            mdinfo = md_simulation.context.getState(True, True, False, True, True, periodic)
            oldPE =  mdinfo.getPotentialEnergy()
            oldKE =  mdinfo.getKineticEnergy()
            if verbose == True:
                log_ncmc = nc_integrator.getLogAcceptanceProbability(nc_context)
                print('before ncmc move log_ncmc', log_ncmc, np.isnan(log_ncmc))
            prev = np.random.randint(2)
            if prev == 1:
                nc_context.setVelocities(-oldVel)
            if 0:
                if self._storage and self.write_ncmc_interval:
                    positions = nc_context.getState(getPositions=True).getPositions(asNumpy=True)
                    self._storage.write_configuration('positions', positions, md_simulation.topology, iteration=stepsdone, frame=0, nframes=(nstepsNC+1))

            for stepscarried in range(nstepsNC):

                if movekey != None:
                    for func in movekey:
                        if stepscarried in func[1]:
                            print('doing the move')
                            func[0]()
#                tempTraj = np.array(())
                if verbose == True and stepscarried == 0:
                    tempPos = nc_stateinfo.getPositions(asNumpy=True)
                    last_x, last_y = np.shape(tempPos)
                    tempTraj = (np.reshape(tempPos, (1, last_x, last_y))).value_in_unit(unit.nanometers)
                    first_ncmc = np.concatenate((first_ncmc, tempTraj))

#                    tempTraj = np.concatenate((tempTraj, temp_frame))


                try:

                    nc_integrator.step(1)
                    if self._storage and self.write_ncmc_interval and ((stepscarried+1) % self.write_ncmc_interval == 0):
                        positions = nc_context.getState(getPositions=True).getPositions(asNumpy=True)
                        assert quantity_is_finite(positions) == True
                        print('writing')
#                        self._storage.write_configuration('positions', positions, md_simulation.topology, iteration=stepsdone, frame=(stepcarried+1), nframes=(nstepsNC+1))
                        self._storage.write_configuration('positions', positions, md_simulation.topology, iteration=stepsdone, frame=0, nframes=(nstepsNC+1))



                except Exception as e:
                    if str(e) == "Particle coordinate is nan":
                        print('nan, breaking')
                        break
                if ncmc_report == True:
                    #edit
                    if stepscarried % 10 == 0:
                        ncmc_reporter.add_temp_traj(nc_context)
                if verbose == True:
                    log_ncmc = nc_integrator.getLogAcceptanceProbability(nc_context)
                    print('log_ncmc', log_ncmc, stepscarried, np.isnan(log_ncmc))
                    nc_stateinfo = nc_context.getState(True, False, False, False, False, periodic)
##                    tempPos = nc_stateinfo.getPositions(asNumpy=True)
                    #connected
                    newinfo = nc_context.getState(True, True, False, True, True, periodic)
                    newPos = newinfo.getPositions(asNumpy=True)
                    #correction = computeAlchemicalCorrection(testsystem, nc_context.getSystem(), oldPos, newPos, direction='insert')
                    #print('correction', correction)
                    ######
##                    last_x, last_y = np.shape(tempPos)
#                    print np.reshape(tempPos, (1, last_x, last_y))
                    temp_frame = (np.reshape(tempPos, (1, last_x, last_y))).value_in_unit(unit.nanometers)
                    if True not in np.isnan(temp_frame) and stepscarried != 0:
#                        ncmc_frame = np.vstack((ncmc_frame, temp_frame))
                        tempTraj = np.concatenate((tempTraj, temp_frame))


                    if np.isnan(log_ncmc) == True:
                        print('nan, breaking')
                        break
                

        # Retrieve the log acceptance probability
##            if verbose == True:
##                ncmc_frame = np.concatenate((ncmc_frame, tempTraj))
            if ncmc_report == True:
                ncmc_reporter.combine_traj()

            log_ncmc = nc_integrator.getLogAcceptanceProbability(nc_context)
            newinfo = nc_context.getState(True, True, False, True, True, periodic)
            newPos = newinfo.getPositions(asNumpy=True)
            newVel = newinfo.getVelocities(asNumpy=True)
            randnum =  math.log(np.random.random())
            if alchemical_correction == True and np.isnan(log_ncmc) == False:
                print('performing correction')
                dummy_simulation.context.setPositions(oldPos)
                dummy_simulation.context.setVelocities(oldVel)
                dummy_info = dummy_simulation.context.getState(True, True, False, True, True, False)#*might want to make this periodic
                md_simulation.context.setPositions(newPos)
                md_simulation.context.setVelocities(newVel)
                md_info_new = md_simulation.context.getState(True, True, False, True, True, False)#*might want to make this periodic

                print('md_energy_orig', oldPE)

                print('md_energy', md_info_new.getPotentialEnergy())               
                print('dummy_energy', dummy_info.getPotentialEnergy())

                dummy_simulation.context.setPositions(newPos)
                reshape = (np.reshape(oldPos, (1, last_x, last_y))).value_in_unit(unit.nanometers)
                dummy_simulation.context.setVelocities(newVel)
                dummy_info = dummy_simulation.context.getState(True, True, False, True, True, False)#*might want to make this periodic
                print('dummy_energy', dummy_info.getPotentialEnergy())
                print('difference', (-newinfo.getPotentialEnergy() + md_info_new.getPotentialEnergy())*(1/nc_integrator.kT))
                log_ncmc = log_ncmc + (-newinfo.getPotentialEnergy() + md_info_new.getPotentialEnergy())*(1/nc_integrator.kT)

            print(log_ncmc, randnum)
            yesAccept = False
            if log_ncmc > randnum:
                print('ncmc move accepted!')
                print('ncmc PE', newinfo.getPotentialEnergy(), 'old PE', oldPE)
                print(newinfo.getPotentialEnergy() + newinfo.getKineticEnergy())
                PE_diff = newinfo.getPotentialEnergy() - oldPE                 
                print('PE_diff', PE_diff)


                randnum1 =  math.log(np.random.random())
                if alchemical_correction == True:
                    log_afterRot = -1.0*(md_info_new.getPotentialEnergy() - oldPE)/nc_integrator.kT
                else:
                    log_afterRot = -1.0*PE_diff / nc_integrator.kT
                print('log_afterRot', log_afterRot)
                otherCounter = otherCounter + 1
                print('otherCounter', otherCounter)

                if log_afterRot > randnum1:
                    print('its cool!', log_afterRot, '>', randnum1)
                    print('move accepted!')
                    accCounter = accCounter + 1.0
                    print('accCounter', float(accCounter)/float(stepsdone+1), accCounter)
                    yesAccept = True
    
                    nc_stateinfo = nc_context.getState(True, True, False, False, False, periodic)
    
                    oldPos = newPos[:]
                    oldVel = newVel[:]
                else:
                    print('bummer', log_afterRot, '<', randnum1)
                    #TODO may want to think about velocity switching on rejection
            else:
                print('move rejected, reversing velocities')
                nc_context.setPositions(oldPos)
                nc_context.setVelocities(-oldVel)
            if prev == 1:
                oldVel = -oldVel
            if yesAccept==False and origPos != None:
                oldPos = origPos

            print('accCounter:', accCounter, 'otherCounter:', otherCounter, 'iter:', stepsdone)
            nc_integrator.reset()
            md_simulation.context.setPositions(oldPos)
            md_simulation.context.setVelocities(oldVel)
#            md_simulation.context.setVelocitiesToTemperature(100)
            if nstepsMD > 0:
                try:
                    md_simulation.step(nstepsMD)
                except Exception as e:
                    print('Error:', e)
                    stateinfo = md_simulation.context.getState(True, True, False, False, False, periodic)
                    #oldPos = stateinfo.getPositions()
                    if ncmc_report == True:
                        print('shape', np.shape(ncmc_reporter.traj))
                        ncmc_reporter.save_traj(output_name='broken_ncmc.dcd', topology=testsystem.topology)
                    if rot_report == True:
                        print(np.shape(rot_reporter.traj))
                
                        rot_reporter.save_traj(output_name='ncmc_rot.gro', topology=testsystem.topology)

                    print(oldPos)
                    last_x, last_y = np.shape(oldPos)
                    print(np.reshape(oldPos, (1, last_x, last_y)))
                    reshape = (np.reshape(oldPos, (1, last_x, last_y))).value_in_unit(unit.nanometers)
                    print(np.shape(reshape))
                    print(newinfo.getPotentialEnergy())
                    print(newinfo.getKineticEnergy())
                    print(oldPE)
                    print(oldKE)

                    last_top = md.Topology.from_openmm(testsystem.topology)
                    broken_frame = md.Trajectory(xyz=reshape, topology=last_top)
                    broken_frame.save_pdb('broken.pdb')
                    print('np.shape', np.shape(broken_frame))
                    broken_ncmc = md.Trajectory(xyz=ncmc_frame, topology=last_top)
                    try:
                        broken_ncmc.save_gro('broken_last.gro')
                    except ValueError:
                        print('couldnt output gro, values too large')
                    try:
                        broken_ncmc.save_dcd('broken_ncmc.dcd')
                    except ValueError:
                        print('couldnt output dcd, values too large')
                    try:
                        broken_ncmc.save_pdb('broken_ncmc.pdb')
                    except ValueError:
                
                        print('couldnt output pdb, values too large')

                    exit()



            md_stateinfo = md_simulation.context.getState(True, True, False, False, False, periodic)
            oldPos = md_stateinfo.getPositions(asNumpy=True)
            oldVel = md_stateinfo.getVelocities(asNumpy=True)
            nc_integrator.reset() #TODO
            nc_context.setPositions(oldPos)
            self.nc_pos = oldPos
            nc_context.setVelocities(oldVel)
            
        #print 'traj', ncmc_reporter.traj
        #print 'traj2', rot_reporter.traj
#        if ncmc_report == True:
        if ncmc_report == True:
            print('shape', np.shape(ncmc_reporter.traj))
            ncmc_reporter.save_traj(output_name='broken_ncmc.dcd', topology=testsystem.topology)
        if rot_report == True:
            print(np.shape(rot_reporter.traj))

            rot_reporter.save_traj(output_name='ncmc_rot.gro', topology=testsystem.topology)

        acceptRatio = accCounter/float(niter)
        print(acceptRatio)
        print(otherCounter)

        print('numsteps ', nstepsNC)
        return oldPos