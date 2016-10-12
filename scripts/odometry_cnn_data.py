#! /usr/bin/env python

import numpy as np
import math
import sys
import eulerangles

def horizontal_split(data, division, overlay, features):
    output = np.empty([division * features, 64, 360 / division + overlay * 2])
    for d in range(division):
        start = d * (360 / division) - (360 / division / 2 + overlay)
        end = d * (360 / division) + (360 / division / 2 + overlay) - 1
        start = (start + 360) % 360
        end = (end + 360) % 360
        for f in range(features):
            if start > end:
                output[d * features + f, ..., (360 / division / 2 + overlay):] = data[f, ..., start:360]
                output[d * features + f, ..., 0:(360 / division / 2 + overlay)] = data[f, ..., 0:end + 1]
            else:
                output[d * features + f, ..., ...] = data[f, ..., start:end + 1]
    return output

def schema_to_dic(data_schema):
    data_dic = {i:[] for i in set(reduce(lambda x,y: x+y,data_schema))}
    for frame_i in range(len(data_schema)):
        for slot_i in range(len(data_schema[frame_i])):
            data_dic[data_schema[frame_i][slot_i]].append({"slot":slot_i, "frame":frame_i})

    return data_dic

def odom_rad_to_deg(odom):
    return odom[0:3] + [odom[i]*180.0/math.pi for i in range(3, 6)]

def odom_deg_to_rad(odom):
    return odom[0:3] + [odom[i]*math.pi/180.0 for i in range(3, 6)]

class Odometry:
    def __init__(self, kitti_pose=[1, 0, 0, 0,
                                     0, 1, 0, 0,
                                     0, 0, 1, 0]):
        assert len(kitti_pose) == 12
        self.dof = [0] * 6
        self.M = np.matrix([[0] * 4, [0] * 4, [0] * 4, [0, 0, 0, 1]], dtype=np.float64)
        for i in range(12):
            self.M[i / 4, i % 4] = kitti_pose[i]
        self.setDofFromM()

    def setDofFromM(self):
        R = self.M[:3, :3]
        self.dof[0], self.dof[1], self.dof[2] = self.M[0, 3], self.M[1, 3], self.M[2, 3]
        self.dof[5], self.dof[4], self.dof[3] = eulerangles.mat2eulerZYX(R)

    def setMFromDof(self):
        self.M[:3, :3] = eulerangles.euler2matXYZ(self.dof[3], self.dof[4], self.dof[5])
        self.M[0, 3], self.M[1, 3], self.M[2, 3] = self.dof[0], self.dof[1], self.dof[2]

    def distanceTo(self, other):
        sq_dist = 0
        for i in range(3):
            sq_dist += (self.dof[i] - other.dof[i]) ** 2
        return math.sqrt(sq_dist)

    def move(self, dof, inverse = False):
        assert len(dof) == 6
        Rt = np.eye(4, 4)
        Rt[:3, :3] = eulerangles.euler2matXYZ(dof[3], dof[4], dof[5])
        for row in range(3):
            Rt[row, 3] = dof[row]
        if inverse:
            Rt = np.linalg.inv(Rt)
        self.M = np.dot(self.M, Rt)
        self.setDofFromM()
        return self

    def __mul__(self, other):
        out = Odometry()
        out.M = self.M * other.M
        out.setDofFromM()
        return out

    def __sub__(self, other):
        out = Odometry()
        out.M = np.linalg.inv(other.M) * self.M
        out.setDofFromM()
        return out

    def __str__(self):
        output = ""
        for i in range(12):
            output += str(self.M[i/4, i%4]) + " "
        return output[:-1]

def load_kitti_poses(file):
    poses = []
    if not hasattr(file, "readlines"):
        file = open(file)
    for line in file.readlines():
        kitti_pose = map(float, line.strip().split())
        o = Odometry(kitti_pose)
        poses.append(o)
    return poses

def get_delta_odometry(odometries, mask = None):
    if mask == None:
        mask = [1]*len(odometries)
    if len(odometries) != len(mask):
        sys.stderr.write("Number of poses (%s) and velodyne frames (%s) differ!\n" % (len(mask), len(odometries)))
    output = [Odometry()]
    last_i = 0
    for i in range(1, min(len(mask), len(odometries))):
        if mask[i] != 0:
            output.append(odometries[i] - odometries[last_i])
            last_i = i
    return output
