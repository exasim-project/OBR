#!/usr/bin/env python3


class CG:
    name = "cg"
    symmetric = True
    option_defaults = {}

    def supports(self, preconditioner):
        pass


class IC:
    name = "icc"
    symmetric = True
    option_defaults = {}


class NoPrecond:
    name = "none"
    symmetric = True
    option_defaults = {}


class IC:
    name = "cholesky"
    symmetric = True
    option_defaults = {}


class BJ:
    name = "bjacbi"
    symmetric = True
    option_defaults = {}


class Multigrid:
    name = "gamg"
    symmetric = True
    option_defaults = {}
