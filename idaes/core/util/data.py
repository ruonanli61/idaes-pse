##############################################################################
# Institute for the Design of Advanced Energy Systems Process Systems
# Engineering Framework (IDAES PSE Framework) Copyright (c) 2018-2019, by the
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
This module contains functions to read and manage data for use in parameter
esitmation, data reconciliation, and validation.
"""

__author__ = "John Eslick"

import logging
import csv
import pandas as pd
import pint

import pyomo.environ as pyo
import warnings

def _strip(tag):
    """
    Tag renaming function to remove whitespace, depending on the csv format
    column heading items can pick up some extra whitespace when read into Pandas
    """
    return tag.strip()

_log = logging.getLogger(__file__)

# Some common unit string conversions, these are ones we've come across that
# are not handeled by pint. We can orginize and refince known unit strings
# more in the future.
_unit_strings = {
    # Pressure
    "PSI":"psi", "PSIA":"psi", "psia":"psi",
    "PSIG":"psig",
    "INWC":"in water", "IN WC":"in water", "IN/WC":"in water",
    '" H2O':"in water",
    "INHG":"in hg", "IN HG":"in hg", "IN/HG":"in hg", "HGA":"in hg",
    "IN HGA":"in hg",
    # Fraction
    "PCT":"percent", "pct":"percent", "PERCT":"percent",
    "PERCT.":"percent", "PCNT":"percent",
    "PPM":"ppm", "PPB":"ppb",
    "% OPEN":"percent open",
    "% CLSD":"percent closed", "% CLOSED":"percent closed",
    # Length
    "IN":"in", "INS":"in", "INCHES":"in", "Inches":"in",
    "FT":"ft", "FEET":"ft", "FOOT":"ft", "Feet":"ft",
    "MILS":"minch",
    # Speed
    "MPH":"mile/hr",
    "IPS":"in/s",
    # Volume
    "KGAL":"kgal",
    # Vol Flow
    "GPM":"gal/min", "gpm":"gal/min",
    "CFM": "ft^3/min", "KCFM": "ft^3/mmin",
    "SCFM": "ft^3/min", "KSCFM":"ft^3/mmin", # be careful with this one
                                             # I don't know how to indicate its
                                             # a volumetric flow at standard
                                             # conditions
    # Angle
    "DEG":"deg",
    # Angular Speed
    "RPM":"rpm",
    # Fequency
    "HZ":"hz",
    # Temperature
    "DEG F":"degF", "Deg F":"degF", "deg F":"degF",
    "DEG C":"degC", "Deg C":"degC", "deg C":"degC",
    "DEGF":"degF", "DegF":"degF",
    "DEGC":"degC", "DegC":"degC",
    # Temperature Difference
    "DELTA DEG F":"delta_degF", "DETLA Deg F":"delta_degF",
    "DETLA deg F":"delta_degF", "DETLA DEG C":"delta_degC",
    "DETLA Deg C":"delta_degC", "DELTA deg C":"delta_degC",
    "DELTA DEGF":"delta_degF", "DELTA DegF":"delta_degF",
    "DELTA degF":"delta_degF", "DELTA DEGC":"delta_degC",
    "DELTA DegC":"delta_degC", "DELTA degC":"delta_degC",
    "Delta DEG F":"delta_degF", "Delta Deg F":"delta_degF",
    "Delta deg F":"delta_degF", "Delta DEG C":"delta_degC",
    "Delta Deg C":"delta_degC", "Delta deg C":"delta_degC",
    "Delta DEGF":"delta_degF", "Delta DegF":"delta_degF",
    "Delta degF":"delta_degF", "Delta DEGC":"delta_degC",
    "Delta DegC":"delta_degC", "Delta degC":"delta_degC",
    "delta DEG F":"delta_degF", "delta Deg F":"delta_degF",
    "delta deg F":"delta_degF", "delta DEG C":"delta_degC",
    "delta Deg C":"delta_degC", "delta deg C":"delta_degC",
    "delta DEGF":"delta_degF", "delta DegF":"delta_degF",
    "delta degF":"delta_degF", "delta DEGC":"delta_degC",
    "delta DegC":"delta_degC", "delta degC":"delta_degC",
    # Energy
    "MBTU":"kbtu",
    # Mass
    "MLB":"klb",
    "K LB":"klb",
    "K LBS":"klb",
    "lb.":"lb",
    # Mass flow
    "TPH":"ton/hr",
    "tph":"ton/hr",
    "KLB/HR":"klb/hr",
    "KPPH":"klb/hr",
    # Current
    "AMP":"amp", "AMPS":"amp", "Amps":"amp", "Amp":"amp",
    "AMP AC":"amp",
    #pH
    "PH":"pH",
    # VARS (volt-amp reactive)
    "VARS":"VAR",
    "MVARS":"MVAR",
}

_guage_pressures = {
    "psig":"psi",
}

_ignore_units = [
    "percent",
    "ppm",
    "ppb",
    "pH",
    "VAR",
    "MVAR",
    "H2O",
    "percent open",
    "percent closed",
]

def unit_convert(x, frm, to=None, system=None, unit_string_map={},
                 ignore_units=[], guage_pressures={}, atm=1.0):
    """Convert the quntity x to a different set of units. X can be a numpy array
    or pandas series. The from unit can is translated into a string that pint
    can recognize by first looking in unit_string_map then looking in
    know aliases defined in this file. If it is neither place it will be given
    to pint as-is. This translation of the unit is done so that data can be read
    in with the original provided units.

    Args:
        x (float, numpy.array, pandas.series): quntity to convert
        frm (str): original unit string
        to (str): new unit string, or specify "system"
        system (str): unit system to covert to, or specify "to"
        unit_string_map (dict): keys are unit strings and values are
            corresponding strings that pint can recognize.  This only applies to
            the from string.
        ignore_units (list, or tuple): units to not convert
        guage_pressures (dict): keys are units strings to be considered guage
            pressures and the values are corresponding absolute pressure units
        atm (float, numpy.array, pandas.series): pressure in atm to add to guage
            pressure to convert it to absolute pressure.  The default is 1.
    Returns:
        (tuple): quantity and unit string
    """
    ureg = pint.UnitRegistry(system=system)
    if frm in unit_string_map:
        frm = unit_string_map[frm]
    elif frm in _unit_strings:
        frm = _unit_strings[frm]
    # Now check for guage pressure
    guage = False
    if frm in guage_pressures:
        guage = True
        frm = guage_pressures[frm]
    elif frm in _guage_pressures:
        guage = True
        frm = _guage_pressures[frm]
    q = ureg.Quantity
    if (frm in _ignore_units) or (frm in ignore_units):
        return (x, frm)
    else:
        try:
            ureg.parse_expression(frm)
        except pint.errors.UndefinedUnitError:
            warnings.warn("In unit conversion, from unit '{}' is not defined."
                " No conversion.".format(frm), UserWarning)
            return (x, frm)
    if to is None:
        y = q(x, ureg.parse_expression(frm)).to_base_units()
    else:
        y = q(x, ureg.parse_expression(frm)).to(to)
    if guage:
        # convert gauge pressure to absolute
        y = y + atm*ureg.parse_expression("atm")
    return (y.magnitude, str(y.units))

def read_data(csv_file, csv_file_metadata, model=None, rename_mapper=None,
              unit_system=None):
    """
    Read CSV data into a Pandas DataFrame.

    The data should be in a form where the first row contains column headings
    where each column is labeled with a data tag, and the first column contains
    data point labels or time stamps. The metadata should be in a csv file where
    the first column is the tag name, the second column is the model refernce (
    which can be empty), the third column is the tag description, and the fourth
    column is the unit of measure string. Any additional information can be
    added to columns after the fourth colum and will be ignored. The units of
    measure should be something that is recoginzed by pint, or in the ailiases
    defind in this file. Any tags not listed in the metadata will be dropped.

    Args:
        csv_file (str): Path of file to read
        csv_file_metadata (str): Path of csv file to read column metadata from
        model (ConcreteModel): Optional model to map tags to
        rename_mapper (function): Optional function to rename tags
        unit_system (str): Optional system of units to atempt convert to

    Returns:
        (DataFrame): A Pandas data frame with tags in columns and rows indexed
            by time.
        (dict): Column metadata, units of measure, description, and model
            mapping information.
    """
    # read file
    df = pd.read_csv(csv_file, parse_dates=True, index_col=0)
    # Drop empty columns
    df.drop(df.columns[df.columns.str.contains("Unnamed")], axis=1, inplace=True)
    df.rename(mapper=_strip, axis='columns', inplace=True)
    if rename_mapper:
        # Change tag names in some systematic way with the function rename_mapper
        df.rename(mapper=rename_mapper, axis='columns', inplace=True)
    metadata = {}
    if csv_file_metadata:
        with open(csv_file_metadata, 'r') as f:
            reader = csv.reader(f)
            for line in reader:
                tag = line[0].strip()
                if rename_mapper:
                    tag = rename_mapper(tag)
                metadata[tag] = {
                    "reference_string":line[1].strip(),
                    "reference":None,
                    "description":line[2].strip(),
                    "units":line[3].strip()}
    # If a model was provided, map the tags with a reference string to the model
    if model:
        for tag, md in metadata.items():
            if md["reference_string"]:
                try:
                    md["reference"] = pyo.Reference(
                        eval(md["reference_string"], {"m":model}))
                except:
                    warnings.warn("Tag refernce {} not found".format(
                        md["reference_string"]), UserWarning)
    # Drop the columns with no metadata (assuming those are columns to ignore)
    for tag in df:
        if not tag in metadata:
            df.drop(tag, axis=1, inplace=True)

    # If unit_system is specified bulk convert everything to that system of units
    # also update the meta data
    if unit_system:
        for tag in df:
            df[tag], metadata[tag]["units"] = unit_convert(
                df[tag], metadata[tag]["units"], system=unit_system)

    return df, metadata
