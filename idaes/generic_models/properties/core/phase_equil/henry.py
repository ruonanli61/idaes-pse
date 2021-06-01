##############################################################################
# Institute for the Design of Advanced Energy Systems Process Systems
# Engineering Framework (IDAES PSE Framework) Copyright (c) 2018-2020, by the
# software owners: The Regents of the University of California, through
# Lawrence Berkeley National Laboratory,  National Technology & Engineering
# Solutions of Sandia, LLC, Carnegie Mellon University, West Virginia
# University Research Corporation, et al. All rights reserved.
#
# Please see the files COPYRIGHT.txt and LICENSE.txt for full copyright and
# license information, respectively. Both files are also available online
# at the URL "https://github.com/IDAES/idaes-pse".
##############################################################################
"""
Methods for calculating fugacity of Henry's Law components

For now, only support mole fraction basis
"""
from pyomo.environ import Var


class ConstantH():

    @staticmethod
    def build_parameters(cobj, p):
        cobj.add_component(
            "henry_ref_"+p,
            Var(initialize=cobj.config.parameter_data["henry_ref"][p],
                doc="Henry coefficient (mole fraction basis) at reference "
                "state for phase "+p))

    @staticmethod
    def return_expression(b, p, j, T=None):
        cobj = b.params.get_component(j)
        H = getattr(cobj, "henry_ref_"+p)

        return H
