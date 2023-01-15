#!/usr/bin/env python3
from flow import FlowProject


@FlowProject.label
def decomposed(job):
    return job.isfile("run/01_decomposePar.log")


@FlowProject.label
def has_generated_mesh(job):
    """TODO check also for .obr files for state of operation"""
    return job.isfile("case/constant/polyMesh/points")


@FlowProject.label
def is_case(job):
    has_ctrlDict = job.isfile("case/system/controlDict")
    return has_ctrlDict


@FlowProject.label
def final(job):
    """jobs that dont have children/variations are considered to be final and
    are thus eligable for execution"""
    return not job.sp.get("has_child")
