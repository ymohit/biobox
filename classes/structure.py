# Copyright (c) 2014-2017 Matteo Degiacomi
#
# SBT is free software ;
# you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation ;
# either version 2 of the License, or (at your option) any later version.
# SBT is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY ;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
# You should have received a copy of the GNU General Public License along with SBT ;
# if not, write to the Free Software Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA.
#
# Author : Matteo Degiacomi, matteothomas.degiacomi@gmail.com

import subprocess
import os
import sys
import random
import string
from copy import deepcopy

import numpy as np
import scipy.signal

import biobox.lib.fastmath as FM  # cython routines
import biobox.lib.interaction as I

class Structure(object):
    '''
    A Structure consists of an ensemble of points in 3D space and some associated properties.
    '''

    def __init__(self, p=np.array([[], []]), r=1.9):
        '''
        Point coordinates and properties data structures are first initialized.
        properties is a dictionary initially containing an entry for 'center' (center of geometry) and 'radius' (average radius of points).

        :param p: coordinates data structure as a mxnx3 numpy array (alternative conformation x atom x 3D coordinate). nx3 numpy array can be supplied, in case a single conformation is present.
        :param r: average radius of every point in dataset (float), or radius of every point (numpy array)
        '''
        if p.ndim == 3:
            self.coordinates = p
            '''numpy array containing an ensemble of alternative coordinates in 3D space'''

        elif p.ndim == 2:
            self.coordinates = np.array([p])
        else:
            raise Exception("ERROR: expected numpy array with 2 or three dimensions, but %s dimensions were found" %p.ndim)

        self.current = 0
        '''index of currently selected conformation'''

        self.points = self.coordinates[self.current]
        '''pointer to currently selected conformation'''

        self.properties = {}
        '''collection of properties. By default, 'center' (geometric center of the Structure) is defined'''

        self.properties['center'] = self.get_center()
        self.properties['radius'] = r  # average radius of every point

    def get(self, prop):
        '''
        return property from properties array

        :param prop: desired property to extract from property dictionary
        :returns: or nan if failed
        '''
        if str(prop) in self.properties:
            return self.properties[str(prop)]
        else:
            # print "property %s not found!"%prop
            return float('nan')

    def set_current(self, pos):
        '''
        select current frame (place frame pointer at desired position)

        :param pos: number of alternative conformation (starting from 0)
        '''
        if pos < self.coordinates.shape[0]:
            self.current = pos
            self.points = self.coordinates[self.current]
            self.properties['center'] = self.get_center()
        else:
            raise Exception("ERROR: position %s requested, but only %s conformations available" %(pos, self.coordinates.shape[0]))

    def add_property(self, name, value):
        '''
        create a new property.

        :param name: name of the new property to add.
        :param value: value of the new property. Can be any data structure.
        '''
        self.properties[name] = value

    def get_xyz(self, indices=[]):
        '''
        get points coordinates.

        :param indices: indices of points to select. If none is provided, all points coordinates are returned.
        :returns: coordinates of all points indexed by the provided indices list, or all of them if no list is provided.
        '''
        if indices == []:
            return self.points
        else:
            return self.points[indices]

    def set_xyz(self, coords):
        '''
        set point coordinates.

        :param coords: array of 3D points
        '''
        self.coordinates[self.current] = deepcopy(coords)
        self.points = self.coordinates[self.current]

    def add_xyz(self, coords):
        '''
        add a new alternative conformation to the database

        :param coords: array of 3D points, or array of arrays of 3D points (in case multiple alternative coordinates must be added at the same time)
        '''
        # self.coordinates numpy array containing an ensemble of alternative
        # coordinates in 3D space

        if self.coordinates.size == 0 and coords.ndim == 3:
            self.coordinates = deepcopy(coords)
            self.set_current(0)

        elif self.coordinates.size == 0 and coords.ndim == 2:
            self.coordinates = deepcopy(np.array([coords]))
            self.set_current(0)

        elif self.coordinates.size > 0 and coords.ndim == 3:
            self.coordinates = np.concatenate((self.coordinates, coords))
            # set new frame to the first of the newly inserted ones
            self.set_current(self.current + 1)

        elif self.coordinates.size > 0 and coords.ndim == 2:
            self.coordinates = np.concatenate((self.coordinates, np.array([coords])))
            # set new frame to the first of the newly inserted ones
            self.set_current(self.current + 1)

        else:
            raise Exception("ERROR: expected numpy array with 2 or three dimensions, but %s dimensions were found" %np.ndim)

    def delete_xyz(self, index):
        '''
        remove one conformation from the conformations database.

        the new current conformation will be the previous one.

        :param index: alternative coordinates set to remove
        '''
        self.coordinates = np.delete(self.coordinates, index, axis=0)
        if index > 0:
            self.set_current(index - 1)
        else:
            self.set_current(0)

    def clear(self):
        '''
        remove all the coordinates.
        '''
        self.coordinates = np.array([[[], []], [[], []]])
        self.points = self.coordinates[0]

    def translate(self, x, y, z):
        '''
        translate the whole structure by a given amount.

        :param x: translation around x axis
        :param y: translation around y axis
        :param z: translation around z axis
        '''

        # if center has not been defined yet (may happen when using
        # subclasses), compute it
        if 'center' not in self.properties:
            self.get_center()

        # translate all points
        self.properties['center'][0] += x
        self.properties['center'][1] += y
        self.properties['center'][2] += z

        self.points[:, 0] += x
        self.points[:, 1] += y
        self.points[:, 2] += z

    def rotate(self, x, y, z):
        '''
        rotate the structure provided angles of rotation around x, y and z axes (in degrees).

        This is a rotation with respect of the origin.
        Make sure that the center of your structure is at the origin, if you don't want to get a translation as well!
        rotating an object being not centered requires to first translate the ellipsoid at the origin, rotate it, and bringing it back.

        :param x: rotation around x axis
        :param y: rotation around y axis
        :param z: rotation around z axis
        '''
        alpha = np.radians(x)
        beta = np.radians(y)
        gamma = np.radians(z)
        Rx = np.array([[1, 0, 0],
                       [0, np.cos(alpha), - np.sin(alpha)],
                       [0, np.sin(alpha), np.cos(alpha)]])
        Ry = np.array([[np.cos(beta), 0, np.sin(beta)],
                       [0, 1, 0],
                       [-np.sin(beta), 0, np.cos(beta)]])
        Rz = np.array([[np.cos(gamma), -np.sin(gamma), 0],
                       [np.sin(gamma), np.cos(gamma), 0],
                       [0, 0, 1]])
        rotation = np.dot(Rx, np.dot(Ry, Rz))
        # multiply rotation matrix with each point of the ellipsoid
        self.apply_transformation(rotation.T)
        self.get_center()

    def apply_transformation(self, M):
        '''
        apply a 3x3 transformation matrix

        :param M: 3x3 transformation matrix (2D numpy array)
        '''
        self.coordinates[self.current, :, :] = np.dot(self.points, M)
        # new memory allocated? Pointer needs to be moved
        self.points = self.coordinates[self.current]

    def get_center(self):
        '''
        compute protein center of geometry (also assigns it to self.center variable).
        '''
        if len(self.points) > 0:
            self.properties['center'] = np.mean(self.points, axis=0)
        else:
            self.properties['center'] = np.array([0.0, 0.0, 0.0])

        return self.properties['center']

    def center_to_origin(self):
        '''
        move the structure so that its center of geometry is at the origin.
        '''
        c = self.get_center()
        self.translate(-c[0], -c[1], -c[2])

    def rgyr(self):
        '''
        compute radius of gyration.
        '''
        d_square = np.sum((self.points - self.get_center())**2, axis=1)
        return np.sqrt(np.sum(d_square) / d_square.shape[0])

    def check_inclusion(self, p):
        '''
        verify whether a given point is inside or outside the shape.

        .. note:: not yet implemented!
        '''
        raise Exception("awww, no implementation yet available for this method...")

    def get_size(self):
        '''
        compute the dimensions of the object along x, y and z.

        .. note: points radii are not kept into account.
        '''
        x = np.max(self.points[:, 0]) - np.min(self.points[:, 0])
        # +self.properties['radius']*2
        y = np.max(self.points[:, 1]) - np.min(self.points[:, 1])
        # +self.properties['radius']*2
        z = np.max(self.points[:, 2]) - np.min(self.points[:, 2])
        return np.array([x, y, z])

    def rotation_matrix(self, axis, theta):
        '''
        compute matrix needed to rotate the system around an arbitrary axis (using Euler-Rodrigues formula).

        :param axis: 3d vector (numpy array), representing the axis around which to rotate
        :param theta: desired rotation angle
        :returns: 3x3 rotation matrix
        '''

        # if rotation angle is equal to zero, no rotation is needed
        if theta == 0:
            return np.identity(3)

        # method taken from
        # http://stackoverflow.com/questions/6802577/python-rotation-of-3d-vector
        axis = axis / np.sqrt(np.dot(axis, axis))
        a = np.cos(theta / 2)
        b, c, d = -axis * np.sin(theta / 2)
        return np.array([[a * a + b * b - c * c - d * d, 2 * (b * c - a * d), 2 * (b * d + a * c)],
                         [2 * (b * c + a * d), a * a + c * c - b * b - d * d, 2 * (c * d - a * b)],
                         [2 * (b * d - a * c), 2 * (c * d + a * b), a * a + d * d - b * b - c * c]])

    def get_principal_axes(self):
        '''
        compute Structure's principal axes.

        :returns: 3x3 numpy array, containing the 3 principal axes ranked from smallest to biggest.
        '''
        # method taken from chempy source code, geometry.py, method
        # getMomentOfInertiaTensor()

        # compute moment of inertia tensor
        I0 = np.zeros((3, 3), np.float64)
        for i in xrange(0, len(self.points), 1):
            mass = 1  # self.mass[atom] / constants.Na
            I0[0, 0] += mass * (self.points[i, 1] * self.points[i, 1] + self.points[i, 2] * self.points[i, 2])
            I0[1, 1] += mass * (self.points[i, 0] * self.points[i, 0] + self.points[i, 2] * self.points[i, 2])
            I0[2, 2] += mass * (self.points[i, 0] * self.points[i, 0] + self.points[i, 1] * self.points[i, 1])
            I0[0, 1] -= mass * self.points[i, 0] * self.points[i, 1]
            I0[0, 2] -= mass * self.points[i, 0] * self.points[i, 2]
            I0[1, 2] -= mass * self.points[i, 1] * self.points[i, 2]

        I0[1, 0] = I0[0, 1]
        I0[2, 0] = I0[0, 2]
        I0[2, 1] = I0[1, 2]

        # Calculate and return the principal moments of inertia and corresponding
        # principal axes for the current geometry.
        e_values, e_vectors = np.linalg.eig(I0)

        indices = np.argsort(e_values)
        e_values = e_values[indices]
        e_vectors = e_vectors.T[indices]

        return e_vectors

    def align_axes(self):
        '''
        Align structure on its principal axes.

        First principal axis aligned along x, second along y and third along z.
        '''

        # this method is inspired from the procedure followed in in VMD's orient package:
        # set I [draw principalaxes $sel]           <--- show/calc the principal axes
        # set A [orient $sel [lindex $I 2] {0 0 1}] <--- rotate axis 2 to match Z
        # $sel move $A
        # set I [draw principalaxes $sel]           <--- recalc principal axes to check
        # set A [orient $sel [lindex $I 1] {0 1 0}] <--- rotate axis 1 to match Y
        # $sel move $A
        # set I [draw principalaxes $sel]           <--- recalc principal axes
        # to check

        # center the Structure
        self.center_to_origin()

        # get principal axes (ranked from smallest to biggest)
        axes = self.get_principal_axes()

        # align smallest principal axis against z axis
        rotvec = np.cross(axes[0], np.array([1, 0, 0]))  # rotation axis
        sine = np.linalg.norm(rotvec)
        cosine = np.dot(axes[0], np.array([1, 0, 0]))
        angle = np.arctan2(sine, cosine)  # angle to rotate around axis

        rotmatrix = self.rotation_matrix(rotvec, angle)
        self.apply_transformation(rotmatrix)

        # compute new principal axes (after previous rotation)
        axes = self.get_principal_axes()

        # align second principal axis against y axis
        rotvec = np.cross(axes[1], np.array([0, 1, 0]))  # rotation axis
        sine = np.linalg.norm(rotvec)
        cosine = np.dot(axes[1], np.array([0, 1, 0]))
        angle = np.arctan2(sine, cosine)  # angle to rotate around axis

        rotmatrix = self.rotation_matrix(rotvec, angle)
        self.apply_transformation(rotmatrix)

    def write_pdb(self, filename, index=[]):
        '''
        write a multi PDB file where every point is a sphere. VdW radius is written into beta factor.

        :param filename: name of file to output
        :param index: list of frame indices to write to file. By default, a multipdb with all frames will be produced.
        '''

        # if a subset of all available frames is requested to be written,
        # select them first
        if len(index) == 0:
            frames = range(0, len(self.coordinates), 1)
        else:
            if np.max(index) < len(self.coordinates):
                frames = index
            else:
                raise Exception("ERROR: requested coordinate index %s, but only %s are available" %(np.max(index), len(self.coordinates)))

        fout = open(filename, "w")

        for f in frames:
            for i in xrange(0, len(self.coordinates[0]), 1):
                if i > 99999:
                    nb = hex(i).split('x')[1]
                else:
                    nb = str(i)
                l = (nb, "SPH", "SPH", "A", np.mod(i, 9999),
                     self.coordinates[f, i, 0],
                     self.coordinates[f, i, 1],
                     self.coordinates[f, i, 2],
                     self.properties['radius'],
                     1.0, "Z")
                L = 'ATOM  %5s  %-4s%-4s%1s%4i    %8.3f%8.3f%8.3f%6.2f%6.2f          %2s\n' % l
                fout.write(L)

            fout.write("END\n")

        fout.close()

    def ccs(self, use_lib=True, impact_path='', impact_options="-Octree -nRuns 32 -cMode sem -convergence 0.01", pdbname="", scale=False, proberad=1.0):
        '''
        compute CCS calling either impact.

        :param use_lib: if true, impact library will be used, if false a system call to impact executable will be performed instead
        :param impact_path: by default, the environment variable IMPACTPATH is sought. This allows redirecting to a specific impact root folder. 
        :param impact_options: flags to be passes to impact executable
        :param pdbname: if a file has been already written, impact can be asked to analyze it
        :param scale: if True, CCS value calculated with PA method is scaled to better match trajectory method.
        :param proberad: radius of probe. Do find out if your impact library already adds this value by default or not (old ones do)!
        :returns: CCS value in A^2. Error return: -1 = input filename not found, -2 = unknown code for CCS calculation\n
                  -3 CCS calculator failed, -4 = parsing of CCS calculation results failed
        '''

        if use_lib and pdbname == "":

            #if True:
            from biobox.classes.ccs import CCS
            try:
                if impact_path == '':

                    try:
                        impact_path = os.path.join(os.environ['IMPACTPATH'], "lib")
                    except KeyError:
                        raise Exception("IMPACTPATH environment variable undefined")

                if "win" in sys.platform:
                    libfile = os.path.join(impact_path, "libimpact.dll")
                else:
                    libfile = os.path.join(impact_path, "libimpact.so")

                C = CCS(libfile=libfile)

            except Exception as e:
                raise Exception(str(e))

            if "atom_ccs" in self.properties.keys():
                radii = self.properties['atom_ccs'] + proberad

            elif (isinstance(self.properties['radius'], list) or type(self.properties['radius']).__module__ == 'numpy') and self.properties['radius'].shape != ():
                radii = self.properties['radius'] + proberad

            else:
                radii = np.ones(len(self.points)) * self.properties['radius'] + proberad

            if scale:
                return C.get_ccs(self.points, radii)[0]
            else:
                return C.get_ccs(self.points, radii, a=1.0, b=1.0)[0]

        # generate random file name to capture CCS software terminal output
        tmp_outfile = random_string(32)
        while os.path.exists(tmp_outfile):
            tmp_outfile = "%s.pdb" % random_string(32)

        if pdbname == "":
            # write temporary pdb file of current structure on which to launch
            # CCS calculation
            filename = "%s.pdb" % random_string(32)
            while os.path.exists(filename):
                filename = "%s.pdb" % random_string(32)

            self.write_pdb(filename, [self.current])

        else:
            filename = pdbname
            # if file was already provided, verify its existence first!
            if os.path.isfile(pdbname) != 1:
                raise Exception("ERROR: %s not found!" % pdbname)

        try:

            if impact_path == '':
                    try:
                        impact_path = os.path.join(os.environ['IMPACTPATH'], "bin")
                    except KeyError:
                        raise Exception("IMPACTPATH environment variable undefined")

            # if using impact, create parameterization file containing a
            # description for Z atoms (pseudoatom name used in this code)
            f = open('params', 'w')

            if 'radius' in self.properties:
                if isinstance(self.properties['radius'], int) or isinstance(self.properties['radius'], float) or isinstance(self.properties['radius'], np.float64):
                    f.write('[ defaults ]\n H 2.2\n C 2.91\n N 2.91\n O 2.91\n P 2.91\n S 2.91\n')
                    f.write('Z %s' % self.properties['radius'])
                    impact_options += " -param params"

            f.close()

            if "win" in sys.platform:
                impact_name = os.path.join(impact_path, "impact.exe")
            else:
                impact_name = os.path.join(impact_path, "impact")

            subprocess.check_call('%s  %s -rProbe %s %s > %s' % (impact_name, impact_options, proberad, filename, tmp_outfile), shell=True)

        except Exception as e:
            raise Exception(str(e))

        #parse output generated by IMPACT and written into a file
        try:
            f = open(tmp_outfile, 'r')
            for line in f:
                w = line.split()
                if len(w) > 0 and w[0] == "CCS":

                    if scale:
                        v = float(w[-2])
                    else:
                        v = float(w[3])

                    break

            f.close()

            # clean temp files if needed
            #(if a filename is provided, don't delete it!)
            os.remove(tmp_outfile)
            if pdbname == "":
                os.remove(filename)

            return v

        except:
            # clean temp files
            os.remove(tmp_outfile)
            if pdbname == "":
                os.remove(filename)

            return -4

    def saxs(self, crysol_path='', crysol_options="-lm 20 -ns 500", pdbname=""):
        '''
        compute SAXS curve using crysol (from ATSAS suite)

        :param crysol_path: path to crysol executable. By default, the environment variable ATSASPATH is sought. This allows redirecting to a specific impact root folder.
        :param crysol_options: flags to be passes to impact executable
        :param pdbname: if a file has been already written, crysol can be asked to analyze it
        :returns: SAXS curve (nx2 numpy array)
        '''

        if crysol_path == '':
            try:
                crysol_path = os.environ['ATSASPATH']
            except KeyError:
                raise Exception("ATSASPATH environment variable undefined")

        if pdbname == "":
            # write temporary pdb file of current structure on which to launch
            # SAXS calculation
            pdbname = "%s.pdb" % random_string(32)
            while os.path.exists(pdbname):
                pdbname = "%s.pdb" % random_string(32)

            self.write_pdb(pdbname, [self.current])

        else:
            # if file was already provided, verify its existence first!
            if os.path.isfile(pdbname) != 1:
                raise Exception("ERROR: %s not found!" % pdbname)

        # get basename for output
        outfile = os.path.basename(pdbname).split('.')[0]

        call_line = os.path.join(crysol_path,"crysol")
        try:
            subprocess.check_call('%s %s %s >& /dev/null' %(call_line, crysol_options, pdbname), shell=True)
        except Exception as e:
            raise Exception("ERROR: crysol calculation failed!")

        data = np.loadtxt("%s00.int" % outfile, skiprows=1)
        try:
            os.remove("%s00.alm" % outfile)
            os.remove("%s00.int" % outfile)
            os.remove("%s00.log" % outfile)
            os.remove("%s.pdb" % outfile)
        except Exception, ex:
            pass

        return data[:, 0:2]

    def convex_hull(self):
        '''
        compute Structure's convex Hull using QuickHull algorithm.

        .. note:: Qhull available only on scipy >=0.12

        :returns: :func:`Structure <structure.Structure>` object, containing the coordinates of vertices composing the convex hull
        '''
        try:
            from scipy.spatial import ConvexHull
            verts = ConvexHull(self.points)
            return Structure(verts)

        except Exception as e:
            raise Exception("Quick Hull algorithm available in scipy >=0.12!")

    def get_surface_c(self, targets=[], probe=1.4,
                      n_sphere_point=960, threshold=0.05):
        '''
        compute the accessible surface area using the Shrake-Rupley algorithm ("rolling ball method")

        :param targets: indices to be used for surface estimation. By default, all indices are kept into account.
        :param probe: radius of the "rolling ball"
        :param n_sphere_point: number of mesh points per atom
        :param threshold: fraction of points in sphere, above which structure points are considered as exposed
        :returns: accessible surface area in A^2
        :returns: mesh numpy array containing the found points forming the accessible surface mesh
        :returns: IDs of surface points
        '''

        # getting radii associated to every atom
        radii = self.properties['radius']
        if not (isinstance(radii, list) or type(radii).__module__ == 'numpy'):
            radii = np.ones(len(self.points)) * self.properties['radius']

        if len(radii) != len(self.points):
            raise Exception("ERROR: length vdw radii (%s) and points quantity (%s) mismatch!" %(len(radii), len(self.points)))

        if threshold < 0.0 or threshold > 1.0:
            raise Exception("ERROR: threshold should be a floating point between 0 and 1!")

        if len(targets) == 0:
            return FM.c_get_surface(self.points, radii, probe, n_sphere_point, threshold)
        else:
            return FM.c_get_surface(self.points[targets], radii, probe, n_sphere_point, threshold)

    def get_surface(self, targets=[], probe=1.4, n_sphere_point=960, threshold=0.05):
        '''
        compute the accessible surface area using the Shrake-Rupley algorithm ("rolling ball method")

        :param targets: indices to be used for surface estimation. By default, all indices are kept into account.
        :param probe: radius of the "rolling ball"
        :param n_sphere_point: number of mesh points per atom
        :param threshold: fraction of points in sphere, above which structure points are considered as exposed
        :returns: accessible surface area in A^2
        :returns: mesh numpy array containing the found points forming the accessible surface mesh
        :returns: IDs of surface points
        '''

        if len(targets) == 0:
            targets = xrange(0, len(self.points), 1)

        # getting radii associated to every atom
        radii = self.properties['radius']
        if not (isinstance(radii, list) or type(radii).__module__ == 'numpy'):
            radii = np.ones(len(self.points)) * self.properties['radius']

        if len(radii) != len(self.points):
            raise Exception("ERROR: length vdw radii (%s) and points quantity (%s) mismatch!" %(len(radii), len(self.points)))

        if threshold < 0.0 or threshold > 1.0:
            raise Exception("ERROR: threshold should be a floating point between 0 and 1!")

        # create unit sphere points cloud (using golden spiral)
        pts = []
        inc = np.pi * (3 - np.sqrt(5))
        offset = 2 / float(n_sphere_point)
        for k in range(int(n_sphere_point)):
            y = k * offset - 1 + (offset / 2)
            r = np.sqrt(1 - y * y)
            phi = k * inc
            pts.append([np.cos(phi) * r, y, np.sin(phi) * r])

        sphere_points = np.array(pts)
        const = 4.0 * np.pi / len(sphere_points)

        contact_map = I.distance_matrix(self.points, self.points)

        asa = 0.0
        surface_atoms = []
        mesh_pts = []
        # compute accessible surface for every atom
        for i in targets:

            # place mesh points around atom of choice
            mesh = sphere_points * (radii[i] + probe) + self.points[i]

            # compute distance matrix between mesh points and neighboring atoms
            test = np.where(contact_map[i, :] < radii.max() + probe * 2)[0]
            neigh = self.points[test]
            dist = I.distance_matrix(neigh, mesh) - radii[test][:, np.newaxis]

            # lines=atoms, columns=mesh points. Count columns containing values greater than probe*2
            # i.e. allowing sufficient space for a probe to fit completely
            cnt = 0
            for m in range(dist.shape[1]):
                if not np.any(dist[:, m] < probe):
                    cnt += 1
                    mesh_pts.append(mesh[m])

            # calculate asa for current atom, if a sufficient amount of mesh
            # points is exposed (NOTE: to verify)
            if cnt > n_sphere_point * threshold:
                surface_atoms.append(i)
                asa += const * cnt * (radii[i] + probe)**2

        return asa, np.array(mesh_pts), np.array(surface_atoms)

    def get_density(self, step=1.0, sigma=1.0, kernel_half_width=5, buff=3):
        '''
        generate density map from points

        :param step: size of cubic voxels, in Angstrom
        :param sigma: gaussian kernel sigma
        :param kernel_half_width: kernel half width, in voxels
        :param buff: padding to add at points cloud boundaries
        :returns: :func:`Density <density.Density>` object, containing a simulated density map
        '''
        pts = self.points

        # rectangular box boundaries
        bnds = np.array([[np.min(pts[:, 0]) - buff, np.max(pts[:, 0]) + buff],
                         [np.min(pts[:, 1]) - buff, np.max(pts[:, 1]) + buff],
                         [np.min(pts[:, 2]) - buff, np.max(pts[:, 2]) + buff]])

        xax = np.arange(bnds[0, 0], bnds[0, 1] + step, step)
        yax = np.arange(bnds[1, 0], bnds[1, 1] + step, step)
        zax = np.arange(bnds[2, 0], bnds[2, 1] + step, step)

        # create empty box
        d = np.zeros((len(xax), len(yax), len(zax)))

        # place Kronecker deltas in mesh grid
        for p in pts:
            xpos = np.argmin(np.abs(xax - p[0]))
            ypos = np.argmin(np.abs(yax - p[1]))
            zpos = np.argmin(np.abs(zax - p[2]))
            d[xpos, ypos, zpos] = 1

        # create 3d gaussian kernel
        window = kernel_half_width * 2 + 1
        shape = (window, window, window)

        m, n, k = [(ss - 1.) / 2. for ss in shape]

        x_ = np.arange(-m, m + 1, 1).astype(int)
        y_ = np.arange(-n, n + 1, 1).astype(int)
        z_ = np.arange(-k, k + 1, 1).astype(int)
        x, y, z = np.meshgrid(x_, y_, z_)

        h = np.exp(-(x * x + y * y + z * z) / (2. * sigma * sigma))
        h[h < np.finfo(h.dtype).eps * h.max()] = 0
        sumh = h.sum()
        if sumh != 0:
            h /= sumh

        # convolve point mesh with 3d gaussian kernel
        b = scipy.signal.fftconvolve(d, h, mode='same')
        b /= np.max(b)

        # prepare density data structure
        from biobox.classes.density import Density
        D = Density()
        D.properties['density'] = b
        D.properties['size'] = np.array(b.shape)
        D.properties['origin'] = np.mean(self.points, axis=0) - step * np.array(b.shape) / 2.0
        D.properties['delta'] = np.identity(3) * step
        D.properties['format'] = 'dx'
        D.properties['filename'] = ''
        D.properties["sigma"] = np.std(b)

        # D.place_points()

        return D

    def rmsf(self, indices=-1, step=1):
        '''
        compute Root Mean Square Fluctuation (RMSF) of selected atoms.

        :param indices: indices of points for which RMSF will be calculated. If no indices list is provided, RMSF of all points will be calculated.
        :param step: timestep between two conformations (useful when using conformations extracted from molecular dynamics)
        :returns: numpy aray with RMSF of all provided indices, in the same order
        '''

        if self.coordinates.shape[0] < 2:
            raise Exception("ERROR: to compute RMSF several conformations must be available!")

        # if no index is provided, compute RMSF of all points
        if indices == -1:
            indices = np.linspace(0, len(self.coordinates[0, :, 0]) - 1, len(self.coordinates[0, :, 0])).astype(int)

        means = np.mean(self.coordinates[:, indices], axis=0)

        # cumulate all squared distances with respect of mean
        d = []
        for i in xrange(0, self.coordinates.shape[0], 1):
            d.append(np.sum((self.coordinates[i, indices] - means)**2, axis=1))

        # compute square root of sum of mean squared distances
        dist = np.array(d)
        return np.sqrt(np.sum(dist, axis=0) / (float(self.coordinates.shape[0]) * step))

    def pca(self, indices=-1, project_thresh=-1):
        '''
        compute Principal Components Analysis (PCA) on specific points within all the alternative coordinates.

        :param indices: points indices to be considered for PCA
        :param project_thresh: eigenvectors energy value [0,1]. Determines how many vectors are relevant to describe the points main motions,\n
               the higher value, the larger the amount of selected eigenvectors. Every alternative coordinate will be projected in the selected sub-eigenspace.
        :returns: numpy array of ranked eigenvalues
        :returns: numpy array of eigenvectors, ranked according to their eigenvalue
        :returns: optionally returned, when project_thresh is provided as input
        '''

        if project_thresh != -1:
            if project_thresh > 1 or project_thresh <= 0:
                raise Exception("ERROR: project_thresh should be a number between 0 and 1, %s received" % project_thresh)

        # compute displacement matrix (removing mean pos from atom pos in
        # coords matrix)
        coords = self.coordinates[:, indices].reshape(
            (len(self.coordinates), len(indices) * 3)).transpose()

        # check whether conditions for PCA analysis are good
        # if coords.shape[1]<coords.shape[0]:
        #    print "ERROR: found %s conformations and only %s degrees of freedom"%(coords.shape[1], coords.shape[0])
        #    print "ERROR: conformations number should be greater than the system's degrees of freedom (3N)!"
        #    return -1

        disp = deepcopy(coords)
        for i in xrange(0, len(disp), 1):
            disp[i] -= np.mean(disp[i])

        # compute covariance matrix, eigenvalues and eigenvectors
        # print ">> computing covariance matrix..."
        covariance = np.cov(disp)
        # print ">> extracting eigenvalues and eigenvectors (might take few
        # minutes)..."
        [eigenval, eigenvec] = np.linalg.eig(covariance)

        if project_thresh != -1:
            # compute representative number of eigenvectors according to desired ratio (user provided)
            # print "\n   nb., eigenvalue, cumulative ratio"
            # print "   ---------------------------------"
            cumulative = 0
            cnt = 0
            for i in xrange(0, len(eigenval), 1):
                cumulative += eigenval[i]
                # print "   %s, %s, %s"%(i+1, eigenval[i],
                # cumulative/np.sum(eigenval))
                if cumulative / np.sum(eigenval) > project_thresh:
                    cnt = i + 1
                    break

            # compute projection of trajectory on the significant number of eigenvectors
            # lines = n-th eigenvector component, columns = simulation frame
            # print "\n>> projecting trajectory on %s eigenvectors..."%cnt
            p = []
            for i in xrange(0, cnt, 1):
                p.append(np.dot(eigenvec[:, i], coords))

            proj = np.array(p)

            return eigenval, eigenvec, proj

        else:
            return eigenval, eigenvec

    def rmsd_one_vs_all(self, ref_index, points_index=[], align=False):
        '''
        Calculate the RMSD between all structures with respect of a reference structure.
        uses Kabsch alignement algorithm.

        :param ref_index: index of reference structure in conformations database
        :param points_index: if set, only specific points will be considered for comparison
        :param align: if set to true, all conformations will be aligned to reference (note: cannot be undone!)
        :returns: RMSD of all structures with respect of reference structure (in a numpy array)
        '''

        # see: http://www.pymolwiki.org/index.php/Kabsch#The_Code

        bkpcurrent = self.current

        if ref_index >= len(self.coordinates):
            raise Exception("ERROR: index %s requested, but only %s exist in database" %(len(self.coordinates)))

        # define reference frame, and center it
        if len(points_index) == 0:
            m1 = deepcopy(self.coordinates[ref_index])
        elif isinstance(points_index, list) or type(points_index).__module__ == 'numpy':
            m1 = deepcopy(self.coordinates[ref_index, points_index])
        else:
            raise Exception("ERROR: please, provide me with a list of indices to compute RMSD (or no index at all)")

        L = len(m1)
        COM1 = np.sum(m1, axis=0) / float(L)
        m1 -= COM1
        m1sum = np.sum(np.sum(m1 * m1, axis=0), axis=0)

        RMSD = []
        for i in xrange(0, len(self.coordinates), 1):

            if i == ref_index:
                RMSD.append(0.0)
            else:

                # define current frame, and center it
                if len(points_index) == 0:
                    m2 = deepcopy(self.coordinates[i])
                elif isinstance(points_index, list) or type(points_index).__module__ == 'numpy':
                    m2 = deepcopy(self.coordinates[i, points_index])

                COM2 = np.sum(m2, axis=0) / float(L)
                m2 -= COM2

                E0 = m1sum + np.sum(np.sum(m2 * m2, axis=0), axis=0)

                # This beautiful step provides the answer. V and Wt are the orthonormal
                # bases that when multiplied by each other give us the rotation matrix, U.
                # S, (Sigma, from SVD) provides us with the error!  Isn't SVD
                # great!
                V, S, Wt = np.linalg.svd(np.dot(np.transpose(m2), m1))

                # if alignement is required, move pointer to current frame, and
                # apply rotation matrix
                if align:
                    self.set_current(i)
                    rotation = np.dot(V, Wt)
                    self.apply_transformation(rotation)

                reflect = float(
                    str(float(np.linalg.det(V) * np.linalg.det(Wt))))

                if reflect == -1.0:
                    S[-1] = -S[-1]
                    V[:, -1] = -V[:, -1]

                rmsdval = E0 - (2.0 * sum(S))
                rmsdval = np.sqrt(abs(rmsdval / L))

                RMSD.append(rmsdval)

        self.set_current(bkpcurrent)
        return np.array(RMSD)

    def rmsd(self, i, j, points_index=[]):
        '''
        Calculate the RMSD between two structures in alternative coordinates ensemble.
        uses Kabsch alignement algorithm.

        :param i: index of the first structure
        :param j: index of the second structure
        :param points_index: if set, only specific points will be considered for comparison
        :returns: RMSD of the two structures
        '''

        # see: http://www.pymolwiki.org/index.php/Kabsch#The_Code

        if i >= len(self.coordinates):
            raise Exception("ERROR: index %s requested, but only %s exist in database" %(i, len(self.coordinates)))

        if j >= len(self.coordinates):
            raise Exception("ERROR: index %s requested, but only %s exist in database" %(j, len(self.coordinates)))

        # get first structure and center it
        if len(points_index) == 0:
            m1 = deepcopy(self.coordinates[i])
        elif isinstance(points_index, list) or type(points_index).__module__ == 'numpy':
            m1 = deepcopy(self.coordinates[i, points_index])
        else:
            raise Exception("ERROR: give me a list of indices to compute RMSD, or nothing at all, please!")

        # get second structure
        if len(points_index) == 0:
            m2 = deepcopy(self.coordinates[j])
        elif isinstance(points_index, list) or type(points_index).__module__ == 'numpy':
            m2 = deepcopy(self.coordinates[j, points_index])
        else:
            raise Exception("ERROR: give me a list of indices to compute RMSD, or nothing at all, please!")

        L = len(m1)
        COM1 = np.sum(m1, axis=0) / float(L)
        m1 -= COM1
        m1sum = np.sum(np.sum(m1 * m1, axis=0), axis=0)

        COM2 = np.sum(m2, axis=0) / float(L)
        m2 -= COM2

        E0 = m1sum + np.sum(np.sum(m2 * m2, axis=0), axis=0)

        # This beautiful step provides the answer. V and Wt are the orthonormal
        # bases that when multiplied by each other give us the rotation matrix, U.
        # S, (Sigma, from SVD) provides us with the error!  Isn't SVD great!
        V, S, Wt = np.linalg.svd(np.dot(np.transpose(m2), m1))

        reflect = float(str(float(np.linalg.det(V) * np.linalg.det(Wt))))

        if reflect == -1.0:
            S[-1] = -S[-1]
            V[:, -1] = -V[:, -1]

        rmsdval = E0 - (2.0 * sum(S))
        return np.sqrt(abs(rmsdval / L))

    def rmsd_distance_matrix(self, points_index=[], flat=False):
        '''
        compute distance matrix between structures (using RMSD as metric).

        :param points_index: if set, only specific points will be considered for comparison
        :param flat: if True, returns flattened distance matrix
        :returns: RMSD distance matrix
        '''

        if flat:
            rmsd = []
        else:
            rmsd = np.zeros((len(self.coordinates), len(self.coordinates)))

        for i in xrange(0, len(self.coordinates) - 1, 1):
            for j in xrange(i + 1, len(self.coordinates), 1):
                r = self.rmsd(i, j, points_index)

                if flat:
                    rmsd.append(r)
                else:
                    rmsd[i, j] = r
                    rmsd[j, i] = r

        if flat:
            return np.array(rmsd)
        else:
            return rmsd


def random_string(length=32):
    '''
    generate a random string of arbitrary characters. Useful to generate temporary file names.

    :param length: length of random string
    '''
    return ''.join([random.choice(string.ascii_letters)
                    for n in xrange(length)])
