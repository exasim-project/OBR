#!/usr/bin/env python3


class CG:
    name = "PCG"
    symmetric = True
    option_defaults = {}


class NoPrecond:
    name = "none"
    symmetric = True
    option_defaults = {}


class DIC:
    name = "DIC"
    symmetric = True
    option_defaults = {}
