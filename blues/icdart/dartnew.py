import numpy as np
from future.utils import iteritems
from itertools import combinations
import pandas as pd
from rottransedit import dartRotTrans
import copy

def symmetrize(a):
    return a + a.T - np.diag(a.diagonal())


def compare_dihedral_edit(a_dir, b_dir, cutoff=80.0, construction_table=None):
    #originally in radians, convert to degrees
    a_dir, b_dir = np.deg2rad(a_dir), np.deg2rad(b_dir)
    b_cos, b_sin = np.cos(b_dir), np.sin(b_dir)
    a_cos, a_sin = np.cos(a_dir), np.sin(a_dir)
    cos_diff = np.square(b_cos - a_cos)
    sin_diff = np.square(b_sin - a_sin)
    dist = np.sqrt(cos_diff + sin_diff)
    print('DIST', dist)
    print('in rad', np.rad2deg(np.arcsin(dist/2.0)*2))

#    if np.rad2deg(np.arcsin(dist.get_value(i)/2.0)*2) > cutoff:
    if np.rad2deg(np.arcsin(dist/2.0)*2) <= cutoff:
        print('within')
        return 1
    else:
        print('not within')
        #returns 0 if within radius
        return 0

def dihedralDifference(a, b, construction_table=None):
    a_di, b_di = a['dihedral'], b['dihedral']
    a_dir, b_dir = np.deg2rad(a_di), np.deg2rad(b_di)
    b_cos, b_sin = np.cos(b_dir), np.sin(b_dir)
    a_cos, a_sin = np.cos(a_dir), np.sin(a_dir)
    cos_diff = np.square(b_cos - a_cos)
    sin_diff = np.square(b_sin - a_sin)
    dist = np.sqrt(cos_diff + sin_diff)
    print(dist)
    print(dist.to_frame('pose_1'))
    return dist

def makeStorageFrame(dataframe, num_poses):
    dframe = dataframe['dihedral']
    counter=0
    temp_frame = dframe.copy()
    for i in range(num_poses):
        frame_name = 'pose_'+str(i)
        if counter == 0:
            out_frame = dframe.to_frame(frame_name)
        else:
            temp_frame = dframe.to_frame(frame_name)
            #out_frame = pd.concat([out_frame, temp_frame], join='inner')
            out_frame = out_frame.join(temp_frame)
        counter= counter+1
    for j in out_frame.columns:
#        out_frame[:] = out_frame.replace(to_replace=r'\*', value=np.nan)
        #out_frame[:] = np.nan
        out_frame[:] = -1
    aframe = dataframe['atom']
    out_frame = aframe.to_frame('atom').join(out_frame)


    return out_frame


def makeDihedralDifferenceDf(internal_mat, dihedral_cutoff=0.3):
    if dihedral_cutoff < 0:
        raise ValueError('Negative dihedral_cutoff distance does not make sense. Please specify a positive cutoff.')
    diff_dict = {}
    output = makeStorageFrame(internal_mat[0], len(internal_mat))
    for index, zmat in enumerate(internal_mat):
        diff_dict[index] = copy.deepcopy(output)
    for zmat in combinations(internal_mat, 2):
        dist_series = dihedralDifference(zmat[0], zmat[1])
        first_index = internal_mat.index(zmat[0])
        second_index = internal_mat.index(zmat[1])
        sort_index = diff_dict[first_index].index
        print('diff', dist_series)
        print('toFrame', dist_series.to_frame('pose_'+str(first_index)))
        #joining is strange, to make it work properly sort by ascending index first
        diff_dict[first_index] = diff_dict[first_index].sort_index()
        diff_dict[second_index] = diff_dict[second_index].sort_index()
        #join the difference dictionary
        diff_dict[first_index].loc[:,'pose_'+str(second_index)] = dist_series.to_frame('pose_'+str(second_index)).sort_index()
        diff_dict[second_index].loc[:,'pose_'+str(first_index)] = dist_series.to_frame('pose_'+str(first_index)).sort_index()

        #diff_dict[first_index] = diff_dict[first_index].merge( dist_series.to_frame('pose_'+str(second_index)).sort_index(), on=['pose_'+str(second_index)], how='right')
        #diff_dict[second_index] = diff_dict[second_index].merge( dist_series.to_frame('pose_'+str(first_index)).sort_index(), on=['pose_'+str(first_index)], how='right')
        #use the old sorting index
        diff_dict[first_index] = diff_dict[first_index].loc[sort_index]
        diff_dict[second_index] = diff_dict[second_index].loc[sort_index]
    dihedral_dict = {}
    for i in internal_mat[0].index:
        dihedral_dict[i] = []
    #loop over entries in poses and find the distances for each
    for i in internal_mat[0].index[3:]:
        for key, df in iteritems(diff_dict):
            for pose in df.columns[1:]:
                if df['atom'].get_value(i) != 'H':
                    dihedral_dict[i].append(df[pose].get_value(i))
                    #df[pose].get_value(i)>= 0.6

                    print('value', df[pose].get_value(i))

    #remove redundant entries in dict
    for key, di_list in iteritems(dihedral_dict):
        di_list = list(set(di_list))
        #only keep track of the sensible dihedrals (above a small cutoff distance)
        dihedral_dict[key] = [i for i in di_list if i >= dihedral_cutoff]
    #go over all entries and sort by atom#, difference with some cutoff (maybe 40 degrees?)

    #start with one with the largest minimum difference (or maybe just largest difference), above a cutoff


    #need to make dart identification w/ dihedral function
    #using function, identify which poses overlap if any
    #if poses overlap move on to next pose

    ndf = None
    print('first ndf', ndf)
    entry_counter = 0

    for key, di_list in iteritems(dihedral_dict):
        for idx, di in enumerate(di_list):
            print('key, di', [key, di])
            #temp_frame = pd.DataFrame(data=[key, di], columns=['atomnum', 'diff'])
            temp_frame = pd.DataFrame(data={'atomnum':key, 'diff':di}, index=[entry_counter])
            entry_counter = entry_counter +1
            if ndf is None:
                ndf = temp_frame.copy()
            else:
                ndf = ndf.append(temp_frame)
            #temp_frame = pd.DataFrame(data=[key, di], columns=['atomnum', 'diff'])

            print('temp_frame', temp_frame)
            ndf.append(temp_frame)
            print('ndf', ndf)
    #TODO: figure out how to treat duplicate angles
    if entry_counter == 0:
        return None
    ndf = ndf.sort_values(by='diff', ascending=False)
    #change internal_mat to the internal zmat storage variable
    return ndf

def compareDihedral(internal_mat, atom_index, diff_spread, posedart_dict, inRadians=True):
    posedart_copy = copy.deepcopy(posedart_dict)
    #reset counts for dictionary
    for posenum, zmat in enumerate(internal_mat):
        for other_posenum, other_zmat in enumerate(internal_mat):
            posedart_copy['pose_'+str(posenum)]['dihedral'][atom_index] = []
    #iterate over zmat and get original value of pose
    if inRadians==True:
        diff_spread = np.rad2deg(diff_spread)
    for posenum, zmat in enumerate(internal_mat):
        comparison = zmat['dihedral'].get_value(atom_index)
        for other_posenum, other_zmat in enumerate(internal_mat):
            if posenum != other_posenum:
                other_comparison = other_zmat['dihedral'].get_value(atom_index)
                result = compare_dihedral_edit(comparison, other_comparison, cutoff=diff_spread)
                if result == 1:
                    posedart_copy['pose_'+str(posenum)]['dihedral'][atom_index].append(other_posenum)
            else:
                pass
    return posedart_copy

def fcompare_dihedral(a, b, atomnum, cutoff=80.0, construction_table=None):
    a_di, b_di = a['dihedral'].get_value(atomnum), b['dihedral'].get_value(atomnum)

    #originally in radians, convert to degrees
    a_dir, b_dir = np.deg2rad(a_di), np.deg2rad(b_di)
    b_cos, b_sin = np.cos(b_dir), np.sin(b_dir)
    a_cos, a_sin = np.cos(a_dir), np.sin(a_dir)
    cos_diff = np.square(b_cos - a_cos)
    sin_diff = np.square(b_sin - a_sin)
    dist = np.sqrt(cos_diff + sin_diff)
    if np.rad2deg(np.arcsin(dist/2.0)*2) <= cutoff:
        print('within')
        return 1
    else:
        print('not within')
        #returns 0 if within radius
        return 0


def createDihedralDarts(internal_mat, dihedral_df, posedart_dict, dart_storage):
    if dihedral_df is None:
        for key, pose in iteritems(posedart_dict):
            pose['dihedral'] = None
        return dart_storage, posedart_dict, False
    last_repeat = {}
    unison_dict = {}
    for key, pose in iteritems(posedart_dict):
        if pose['translation'] is None:
            trans_overlap_list = None
        else:
            trans_overlap_list = [set(pose['translation'])]
        if pose['rotation'] is None:
            rot_overlap_list = None
        else:
            rot_overlap_list = [set(pose['rotation'])]
        overlap_list = addSet([trans_overlap_list, rot_overlap_list])
        if overlap_list is None:
            last_repeat[key] = None
        elif len(overlap_list) > 0:
            unison = set.intersection(*overlap_list)
            last_repeat[key] = len(unison)
            print('ainital last repeat', last_repeat[key])
        else:
            print('aaatype error')
            last_repeat[key] = {0}-{0}
    print('last_repeat', last_repeat)




    for idx, i in list(zip(dihedral_df.index.tolist(), dihedral_df['atomnum'])):

        print('DEBUG', dihedral_df['diff'])
        print('idx', idx)
        print('pddict', posedart_dict)
        #updates posedart_dict with overlaps of poses for each dart
        posedart_copy = compareDihedral(internal_mat, atom_index=i, diff_spread=dihedral_df['diff'].get_value(idx)/2.0, posedart_dict=posedart_dict)
        #checks if darts separate all poses from each other if still 0
        dart_check = 0

        #check for duplicates
        for key, pose in iteritems(posedart_copy):
            print('KEY', key.split('_')[-1])
    #        overlap_list = list(pose['dihedral'].values())
    #        overlap_list = [oi for oi in list(pose['dihedral'].values()) if len(oi) > 0 ]
            overlap_list = [set(oi) for oi in list(pose['dihedral'].values()) if len(oi) > 0 ]

            print('overlap_list', overlap_list)

    #        for l in overlap_list:
    #            for j in set(l):
    #                if j in seen:
    #                    repeated.add(j)
    #                else:
    #                    seen.add(j)
            try:
                #if there's no overlaps then this will fail
                unison = set.intersection(*overlap_list)
            except TypeError:
                unison = set([])
            unison_dict[key] = len(unison)

            if len(unison) > 0:
                dart_check += 1
                print('repeated for posedart, not cool', unison)
            else:
                print('selected internal coordinates separate all poses')
        dboolean = 0
        for key, value in iteritems(unison_dict):
            print('last_repeat', last_repeat)
            print('value', value, 'last_repeat', last_repeat[key])
            #if last_repeat[key] == set():
            #    dboolean = dboolean + 1
            if last_repeat[key] is None and unison_dict[key] < len(internal_mat):
                dboolean += 1
                #posedart_dict = copy.deepcopy(posedart_copy)
            try:
                if value < last_repeat[key]:
                    dboolean = dboolean + 1
            except TypeError:
                pass
        if dboolean > 0:
            posedart_dict = copy.deepcopy(posedart_copy)
            dart_storage['dihedral'][i] = dihedral_df['diff'].get_value(idx)/2.0
            for key, value in iteritems(unison_dict):
                last_repeat[key] = unison_dict[key]


        #counts all poses and sees if no overlap (-=0)is true for all
        #If so, stop loop
        if dart_check == 0:
            return dart_storage, posedart_dict, True
    return dart_storage, posedart_dict, False

def compareTranslation(trans_mat, trans_spread, posedart_dict, dart_type='translation'):
    posedart_copy = copy.deepcopy(posedart_dict)
    num_poses = np.shape(trans_mat)[0]
    compare_indices = np.triu_indices(num_poses)
    #reset counts for dictionary
    for apose in range(num_poses):
            posedart_copy['pose_'+str(apose)][dart_type] = []

    for pose1, pose2 in zip(compare_indices[0], compare_indices[1]):
        if pose1 != pose2:
            if trans_mat[pose1, pose2] < trans_spread:
                #if less, then the other centroid is within the radius and we need to add
                posedart_copy['pose_'+str(pose1)][dart_type].append(pose2)
                posedart_copy['pose_'+str(pose2)][dart_type].append(pose1)
            else:
                pass


    #iterate over zmat and get original value of pose
    return posedart_copy

def compareRotation(rot_mat, rot_spread, posedart_dict, dart_type='rotation'):
    posedart_copy = copy.deepcopy(posedart_dict)
    num_poses = np.shape(rot_mat)[0]
    compare_indices = np.triu_indices(num_poses)
    #reset counts for dictionary
    for apose in range(num_poses):
            posedart_copy['pose_'+str(apose)][dart_type] = []

    for pose1, pose2 in zip(compare_indices[0], compare_indices[1]):
        if pose1 != pose2:
            if rot_mat[pose1, pose2] < rot_spread:
                #if less, then the other centroid is within the radius and we need to add
                posedart_copy['pose_'+str(pose1)][dart_type].append(pose2)
                posedart_copy['pose_'+str(pose2)][dart_type].append(pose1)
            else:
                pass


    #iterate over zmat and get original value of pose
    return posedart_copy
def getRotTransMatrices(internal_mat, pos_list, construction_table):
    trans_storage = np.zeros( (len(internal_mat), len(internal_mat)) )
    rot_storage = np.zeros( (len(internal_mat), len(internal_mat)) )
    for zindex in combinations(list(range(len(internal_mat))), 2):
        first_index = zindex[0]
        second_index = zindex[1]
        temp_rot, temp_trans = dartRotTrans(binding_mode_pos=pos_list, internal_zmat=internal_mat,
                                 binding_mode_index=first_index, comparison_index=second_index,
                                 construction_table=construction_table )
        print('temp_trans', temp_trans)
        if np.isnan(temp_rot):
        #only be nan if due to rounding error due to no rotation
            rot_storage[zindex[0], zindex[1]] = 0
        else:
            rot_storage[zindex[0], zindex[1]] = temp_rot

        trans_storage[zindex[0], zindex[1]] = temp_trans
        trans_storage = symmetrize(trans_storage)/ 2.0
        rot_storage = symmetrize(rot_storage) / 2.0
    return rot_storage, trans_storage


def findInternalDart(sim_mat, internal_mat, dart_storage):
    """function used to check if a pose from the simulation
    matches a pose from the original poses"""
    dart_list = [0 for p in internal_mat]
    total_counter = sum(len(v) for v in dart_storage.itervalues())
    for index, pose in enumerate(internal_mat):
        dart_counter = 0
        for selection in ['bond', 'angle', 'dihedral' ]:
            if selection == 'dihedral':
                    for atomnum, di in iteritems(dart_storage['dihedral']):
                        print('pose!', pose['dihedral'].get_value(atomnum))
                        #inorout = compare_dihedral(sim_mat, pose['dihedral'].get_value(atomnum), cutoff=di, )

                        inorout = fcompare_dihedral(sim_mat, pose, atomnum, cutoff=di, )
                        dart_counter =+ inorout

        dart_list[index] = dart_counter
    print('dart_list', dart_list)
    for item in dart_list:
        if item == total_counter:
            print('pose found')

def addSet(set_list):
    add_return = None
    for i in set_list:
        if add_return is None:
            add_return = i
        elif i != None:
            add_return = add_return + i
    return add_return

def createTranslationDarts(internal_mat, trans_mat, posedart_dict, dart_storage):
    #need to know how many regions are separated to see if adding translational darts improve things
    dihedral_present = True
    #rotation_present = True
    last_repeat = {}
    unison_dict = {}
    for key, pose in iteritems(posedart_dict):
        print('KEY', key.split('_')[-1])
        #trans_overlap_list = [set(pose['translation'])]
        #rot_overlap_list = [set(pose['rotation'])]
        #overlap_list = di_overlap_list+trans_overlap_list+rot_overlap_list
        try:
            di_overlap_list = [set(oi) for oi in list(pose['dihedral'].values()) if len(oi) > 0 ]
            print('di_overlap debug', di_overlap_list)
            #if there's no overlaps then this will fail
            if len(di_overlap_list) > 0:
                unison = set.intersection(*di_overlap_list)
            else:
                last_repeat[key] = 0
        except AttributeError:
            unison = set([])
            last_repeat[key] = None
            dihedral_present = False

    trans_indices = np.triu_indices(len(internal_mat))
    trans_list = sorted([trans_mat[i,j] for i,j in zip(trans_indices[0], trans_indices[1])], reverse=True)
    print('trans_mat', trans_mat)

    #this removes distances less than 1.0 from being used in finding a dart
    #change if really small translational darts are desired
    #without this then dart sizes of 0 can be accepted, which don't make sense
    trans_list = [i for i in trans_list if i > 1.0]
    if len(trans_list) > 0:
        for trans_diff in trans_list:

            print('pddict', posedart_dict)
            #updates posedart_dict with overlaps of poses for each dart
            posedart_copy = compareTranslation(trans_mat=trans_mat, trans_spread=trans_diff, posedart_dict=posedart_dict)
            dart_check = 0

            #check for duplicates
            for key, pose in iteritems(posedart_copy):
                print('KEY', key.split('_')[-1])
        #        overlap_list = list(pose['dihedral'].values())
        #        overlap_list = [oi for oi in list(pose['dihedral'].values()) if len(oi) > 0 ]
                if dihedral_present == True:
                    di_overlap_list = [set(oi) for oi in list(pose['dihedral'].values()) if len(oi) > 0 ]
                else:
                    di_overlap_list = None
                print('posedart_copy', posedart_copy)
                trans_overlap_list = [set(pose['translation'])]
                print('trans_overlap_list', trans_overlap_list)
                overlap_list = addSet([di_overlap_list, trans_overlap_list])


                print('overlap_list', overlap_list)

        #        for l in overlap_list:
        #            for j in set(l):
        #                if j in seen:
        #                    repeated.add(j)
        #                else:
        #                    seen.add(j)
                try:
                    #if there's no overlaps then this will fail
                    unison = set.intersection(*overlap_list)
                except TypeError:
                    unison = set([])
                unison_dict[key] = len(unison)
                if len(unison) > 0 and last_repeat[key] is not None:
                    dart_check += 1
                    last_repeat[key] = len(unison)
                    print('repeats for posedart, not cool', unison)
                #TODO: check if this is even necessary
                elif last_repeat[key] is None and len(unison) < len(internal_mat) and len(unison) > 0:
                    dart_check += 1
                    posedart_dict = copy.deepcopy(posedart_copy)
                    #TODO decide if it should be in angles or radians
                    dart_storage['translation'] = [trans_diff]
                    last_repeat[key] = len(unison)

                elif len(unison) == 0:
                    print('selected internal coordinates separate all poses')
            dboolean = 0
            for key, value in iteritems(unison_dict):
                print('last_repeat', last_repeat)
                if value < last_repeat[key]:
                    dboolean = dboolean + 1
            if dboolean > 0:
                dart_storage['translation'] = [trans_diff]
                posedart_dict = copy.deepcopy(posedart_copy)
            #if adding a dart doesn't reduce amount of overlap, don't keep that dart
            else:
                pass
            #counts all poses and sees if no overlap (-=0)is true for all
            #If so, stop loop
            if dart_check == 0:
                print('all separated, good to go')
                dart_storage['translation'] = [trans_diff]

                return dart_storage, posedart_dict, True
    else:
        for key, pose in iteritems(posedart_dict):
            pose['translation'] = None


    return dart_storage, posedart_dict, False

def createRotationDarts(internal_mat, rot_mat, posedart_dict, dart_storage):
    dihedral_present = True
    translation_present = True
    last_repeat = {}
    unison_dict = {}
    for key, pose in iteritems(posedart_dict):
        print('KEY', key.split('_')[-1])
        #trans_overlap_list = [set(pose['translation'])]
        #rot_overlap_list = [set(pose['rotation'])]
        #overlap_list = di_overlap_list+trans_overlap_list+rot_overlap_list
        try:
            di_overlap_list = [set(oi) for oi in list(pose['dihedral'].values()) if len(oi) > 0 ]
        except AttributeError:
            di_overlap_list = None
            dihedral_present = False
        if pose['translation'] is None:
            trans_overlap_list = None
            translation_present = False

        else:
            trans_overlap_list = [set(pose['translation'])]

#        try:
#            trans_overlap_list = [set(pose['translation'])]
#        except TypeError:
#            trans_overlap_list = None
#            translation_present = False

        #trans_overlap_list = [set(pose['translation'])]
        overlap_list = addSet([di_overlap_list, trans_overlap_list])
        print('overlap_list before', overlap_list)
        if overlap_list is None:
            last_repeat[key] = None
        elif len(overlap_list) > 0:
            unison = set.intersection(*overlap_list)
            last_repeat[key] = len(unison)
            print('ainital last repeat', last_repeat[key])
        else:
            print('aaatype error')
            last_repeat[key] = {0}-{0}




    #need to know how many regions are separated to see if adding translational darts improve things
    rot_indices = np.triu_indices(len(internal_mat))
    rot_list = sorted([rot_mat[i,j] for i,j in zip(rot_indices[0], rot_indices[1])], reverse=True)
    #this removes distances less than 0.1 from being used in finding a dart
    #change if really small translational darts are desired
    #without this then dart sizes of 0 can be accepted, which don't make sense
    rot_list = [i for i in rot_list if i > 0.1]
    print('ROT_LIST', rot_list)


    for rot_diff in rot_list:

        print('pddict', posedart_dict)
        #updates posedart_dict with overlaps of poses for each dart
        posedart_copy = compareRotation(rot_mat=rot_mat,rot_spread=rot_diff, posedart_dict=posedart_dict)
        print('pddict after', posedart_dict)

        dart_check = 0

        #check for duplicates
        for key, pose in iteritems(posedart_copy):
            print('KEY', key.split('_')[-1])
            print('rotation used', rot_diff)
    #        overlap_list = list(pose['dihedral'].values())
    #        overlap_list = [oi for oi in list(pose['dihedral'].values()) if len(oi) > 0 ]
            if dihedral_present == True:
                di_overlap_list = [set(oi) for oi in list(pose['dihedral'].values()) if len(oi) > 0 ]
            else:
                di_overlap_list = None
            if translation_present == True:
                trans_overlap_list = [set(pose['translation'])]
            else:
                trans_overlap_list = None
            print('posedart_copy', posedart_copy)
            print('trans_overlap_list', trans_overlap_list)
            rot_overlap_list = [set(pose['rotation'])]
            print('rot_overlap_list', rot_overlap_list)

            overlap_list = addSet([di_overlap_list, trans_overlap_list, rot_overlap_list])


            print('overlap_list', overlap_list)

    #        for l in overlap_list:
    #            for j in set(l):
    #                if j in seen:
    #                    repeated.add(j)
    #                else:
    #                    seen.add(j)
            try:
                #if there's no overlaps then this will fail
                unison = set.intersection(*overlap_list)

            except TypeError:
                unison = set([])
            unison_dict[key] = len(unison)
            #check number of overlaps
            #if number of overlaps is > 0 note that
            #if no overlaps were present because this is the first check
            #then note that and update last overlaps and posedart dict
            if len(unison) > 0 and last_repeat[key] is not None:
                dart_check += 1
                last_repeat[key] = len(unison)
                print('repeats for posedart, not cool', unison)
            elif last_repeat[key] is None and len(unison) < len(internal_mat) and len(unison) > 0:
                dart_check += 1
                posedart_dict = copy.deepcopy(posedart_copy)
                print(' last repeat', last_repeat[key])
                print(last_repeat)
                print('saving darts')
                #TODO decide if it should be in angles or radians
                dart_storage['rotation'] = [rot_diff]
                last_repeat[key] = len(unison)
            elif len(unison) == 0:
                print('selected internal coordinates separate all poses')
        #check if adding additional regions removes overlaps

        dboolean = 0
        for key, value in iteritems(unison_dict):
            print('last_repeat', last_repeat)
            print('value', value, 'last_repeat', last_repeat[key])
            #if last_repeat[key] == set():
            #    dboolean = dboolean + 1
            try:
                if value < last_repeat[key]:
                    dboolean = dboolean + 1
            #type error if last_repeat is a set or None
            except TypeError:
                pass
        print('dart_boolean', dboolean)

        if dboolean > 0:
            dart_storage['rotation'] = [rot_diff]
            posedart_dict = copy.deepcopy(posedart_copy)
        #if adding a dart doesn't reduce amount of overlap, don't keep that dart
        else:
            pass
        #counts all poses and sees if no overlap (-=0)is true for all
        #If so, stop loop
        print('posedart_after', posedart_dict)
        print('dart_check', dart_check)
        if dart_check == 0:
            dart_storage['rotation'] = [rot_diff]
            print('dart_output', dart_storage)
            return dart_storage, posedart_dict, True
    return dart_storage, posedart_dict, False



def makeDartDict(internal_mat, pos_list, construction_table, dihedral_cutoff=0.5):
    """
    internal_mat: list of zmats
    """
    #make diff dict
    dihedral_df = makeDihedralDifferenceDf(internal_mat, dihedral_cutoff=dihedral_cutoff)
    posedart_dict = {'pose_'+str(posnum):{}  for posnum, value in enumerate(internal_mat)}

    for key, value in iteritems(posedart_dict):
        value['bond'] = {}
        value['angle'] = {}
        value['dihedral'] = {}
        value['rotation'] = None
        value['translation'] = None
        try:
            for atomnum in dihedral_df['atomnum']:
                value['dihedral'][atomnum] = []
        except TypeError:
            pass


    dart_storage = {'bond':{}, 'angle':{}, 'dihedral':{}, 'translation':[], 'rotation':[]}
    dart_storage, posedart_dict, dart_boolean = createDihedralDarts(internal_mat, dihedral_df, posedart_dict, dart_storage)
    #if dart_boolean is false, we need to continue looking thru rot/trans for better separation
    if dart_boolean == False:
        print('doing the trans')
        rot_mat, trans_mat = getRotTransMatrices(internal_mat, pos_list, construction_table)
        print('rot_mat', rot_mat)
        dart_storage, posedart_dict, dart_boolean = createTranslationDarts(internal_mat, trans_mat, posedart_dict, dart_storage)
        if dart_boolean == False:
            print('doing the rot')
            dart_storage, posedart_dict, dart_boolean = createRotationDarts(internal_mat, rot_mat, posedart_dict, dart_storage)
        #check translation
        pass
    print('dict at end', posedart_dict)
    for key in ['rotation', 'translation']:
        if len(dart_storage[key]) > 0:
            dart_storage[key][0] = dart_storage[key][0] - dart_storage[key][0] / 10.0
    return dart_storage

    #get rotation/translation diff matrix
    #start with dihedral, loop over diffs and check overlap

def getNumDarts(dart_storage):
    dart_counter = 0
    print('vlaues', dart_storage.values())
    for value in dart_storage.values():
        if isinstance(value, list):
            if len(value) > 0:
                    dart_counter += 1
        if isinstance(value, dict):
            if len(value.keys()) > 0:
                for valuevalue in value.values():
                    dart_counter += 1
    return dart_counter


def checkDart(internal_mat, current_pos, current_zmat, pos_list, construction_table, dart_storage):

    def createTranslationDarts(internal_mat, trans_mat, dart_storage):
        num_poses = np.shape(trans_mat)[0]
        trans_list = [trans_mat[0,j] for j in range(1, num_poses)]
        #this removes distances less than 1.0 from being used in finding a dart
        #change if really small translational darts are desired
        #without this then dart sizes of 0 can be accepted, which don't make sense
        if len(dart_storage['translation']) > 0:
            trans_cutoff = dart_storage['translation'][0]
            trans_list = [j for j,i in enumerate(trans_list) if i < trans_cutoff]
            return trans_list
        else:
            return None
    def compareRotation(rot_mat, internal_mat, dart_storage):
        print('rot_mat', rot_mat)
        if len(dart_storage['rotation']) > 0:

            rot_cutoff = dart_storage['rotation'][0]
            num_poses = np.shape(rot_mat)[0]
            rot_list = [rot_mat[0,j] for j in range(1, num_poses)]
            print('rot_list options', rot_list)

            rot_list = [j for j,i in enumerate(rot_list) if i < rot_cutoff]
            print('rot_list after', rot_list)

            print('rot_cutoff', rot_cutoff)
            return rot_list
        else:
            return None

    def compareDihedral(current_internal, internal_mat, dart_storage, inRadians=True):
        #reset counts for dictionary
        #iterate over zmat and get original value of pose
        print('n_darts', n_darts)

        dihedral_output = {}
        #num_poses = len(internal_mat)
        dihedral_atoms = list(dart_storage['dihedral'].keys())
        print(dihedral_atoms)
        if len(dihedral_atoms) > 0:
            for atom_index in dihedral_atoms:
                dihedral_output[atom_index] = []
                current_dihedral = current_internal['dihedral'].get_value(atom_index)

                for posenum, zmat in enumerate(internal_mat):
                    comparison = zmat['dihedral'].get_value(atom_index)
                    dihedral_diff = abs(current_dihedral - comparison)

                    if dihedral_diff <= np.rad2deg(dart_storage['dihedral'][atom_index]):
                        dihedral_output[atom_index].append(posenum)


            dihedral_list = []
            for entry in dihedral_output.values():
                dihedral_list.append(*entry)
            return dihedral_list
        else:
            return None
    n_darts = getNumDarts(dart_storage)
    combo_list = [current_pos] + pos_list
    combo_zmat = [current_zmat] + internal_mat

    rot_mat, trans_mat = getRotTransMatrices(combo_zmat, combo_list, construction_table)
    trans_list = createTranslationDarts(combo_zmat, trans_mat, dart_storage)
    print('trans_list', trans_list)

    rot_list = compareRotation(rot_mat, combo_zmat, dart_storage)
    #TODO: from current_internal get current_pos
#    dihedral_output = compareDihedral(zmat_dummy, internal_mat, dart_storage)
    dihedral_output = compareDihedral(current_zmat, internal_mat, dart_storage)

    print('trans_list', trans_list)
    print('dihedral_output', dihedral_output)
    print('rot_list', rot_list)
    print('current_pos', current_pos)
    print('initial_pose', pos_list[0])
    set_output = (addSet([dihedral_output, rot_list, trans_list]))
    #if set_output is not None and len(set_output) ==
    print('set_output', set_output)
    if n_darts == len(set_output) and len(set(set_output)) == 1:
        print('ahhahahahahaaha')
    return set_output





