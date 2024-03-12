"""Data for transport modes and technologies outside of LDVs."""

import logging
from functools import lru_cache
from operator import itemgetter
from typing import TYPE_CHECKING, Dict, List, Mapping

import pandas as pd
from genno import Computer, Key, KeySeq, MissingKeyError, Quantity, quote
from genno.core.key import KeyLike, iter_keys, single_key
from message_ix import make_df
from message_ix_models.util import (
    broadcast,
    make_io,
    make_matched_dfs,
    merge_data,
    private_data_path,
    same_node,
    same_time,
)
from sdmx.model.v21 import Code

from .emission import ef_for_input

if TYPE_CHECKING:
    from message_ix_models import Context

    from .config import Config

log = logging.getLogger(__name__)


#: Target units for data produced for non-LDV technologies.
#:
#: .. todo: this should be read from general model configuration.
UNITS = dict(
    # Appearing in input file
    inv_cost="GUSD_2010 / (Gv km)",  # Gv km of CAP
    fix_cost="GUSD_2010 / (Gv km)",  # Gv km of CAP
    var_cost="GUSD_2010 / (Gv km)",  # Gv km of ACT
    technical_lifetime="a",
    input="1.0 GWa / (Gv km)",
    output="Gv km",
    capacity_factor="",
)

ENERGY_OTHER_HEADER = """2020 energy demand for OTHER transport

Source: Extracted from IEA EWEB, 2022 OECD edition

Units: TJ
"""


def prepare_computer(c: Computer):
    from .key import n, t_modes, y

    context: "Context" = c.graph["context"]
    source = context.transport.data_source.non_LDV
    log.info(f"non-LDV data from {source}")

    keys: List[KeyLike] = []

    if source == "IKARUS":
        keys.append("transport nonldv::ixmp+ikarus")
    elif source is None:
        pass  # Don't add any data
    else:
        raise ValueError(f"Unknown source for non-LDV data: {source!r}")

    # Dummy/placeholder data for 2-wheelers (not present in IKARUS)
    keys.append(single_key(c.add("transport 2W::ixmp", get_2w_dummies, "context")))

    # Compute CO₂ emissions factors
    for k in map(Key, list(keys[:-1])):
        c.add(k + "input", itemgetter("input"), k)
        c.add(k + "emi", ef_for_input, "context", k + "input", species="CO2")
        keys.append(k + "emi")

    # Data for usage technologies
    k_usage = "transport nonldv usage::ixmp"
    keys.append(k_usage)
    c.add(k_usage, usage_data, "load factor nonldv:t:exo", t_modes, n, y)

    # Data for non-specified transport technologies

    #### NB lines below duplicated from .transport.base
    e_iea = Key("energy:n-y-product-flow:iea")
    e_fnp = KeySeq(e_iea.drop("y"))
    e = KeySeq("energy:commodity-flow-node_loc:iea")

    # Transform IEA EWEB data for comparison

    c.add(e_fnp[0], "select", e_iea, indexers=dict(y=2020), drop=True)
    c.add(e_fnp[1], "aggregate", e_fnp[0], "groups::iea to transport", keep=False)
    c.add(
        e[0],
        "rename_dims",
        e_fnp[1],
        quote(dict(n="node_loc", product="commodity")),
        sums=True,
    )
    ####
    c.add(e[1] / "flow", "select", e[0], indexers=dict(flow="OTHER"), drop=True)
    path = private_data_path("transport", context.regions, "energy-other.csv")
    kw = dict(header_comment=ENERGY_OTHER_HEADER)
    c.add("energy other csv", "write_report", e[1] / "flow", path=path, kwargs=kw)

    # Handle data from the file energy-transport.csv
    try:
        k = Key("energy:c-nl:transport other")
        keys.extend(iter_keys(c.apply(other, k)))
    except MissingKeyError:
        log.warning(f"No key {k!r}; unable to add data for 'transport other *' techs")

    # Add minimum activity for transport technologies
    keys.extend(iter_keys(c.apply(bound_activity_lo)))

    # Add to the scenario
    k_all = "transport nonldv::ixmp"
    c.add(k_all, "merge_data", *keys)
    c.add("transport_data", __name__, key=k_all)


def get_2w_dummies(context) -> Dict[str, pd.DataFrame]:
    """Generate dummy, equal-cost output for 2-wheeler technologies.

    **NB** this is analogous to :func:`.ldv.get_dummy`.
    """
    # Information about the target structure
    info = context["transport build info"]

    # List of years to include
    years = list(filter(lambda y: y >= 2010, info.set["year"]))

    # List of 2-wheeler technologies
    all_techs = context.transport.set["technology"]["add"]
    techs = list(map(str, all_techs[all_techs.index("2W")].child))

    # 'output' parameter values: all 1.0 (ACT units == output units)
    # - Broadcast across nodes.
    # - Broadcast across LDV technologies.
    # - Add commodity ID based on technology ID.
    output = (
        make_df(
            "output",
            value=1.0,
            commodity="transport vehicle 2w",
            year_act=years,
            year_vtg=years,
            unit="Gv * km",
            level="useful",
            mode="all",
            time="year",
            time_dest="year",
        )
        .pipe(broadcast, node_loc=info.N[1:], technology=techs)
        .pipe(same_node)
    )

    # Add matching data for 'capacity_factor' and 'var_cost'
    data = make_matched_dfs(output, capacity_factor=1.0, var_cost=1.0)
    data["output"] = output

    return data


def bound_activity_lo(c: Computer) -> List[Key]:
    @lru_cache
    def techs_for(mode: Code, commodity: str) -> List[Code]:
        """Return techs that are (a) associated with `mode` and (b) use `commodity`."""
        result = []
        for t in mode.child:
            if input_info := t.eval_annotation(id="input"):
                if input_info["commodity"] == commodity:
                    result.append(t.id)
        return result

    def _(nodes, technologies, y0, config: dict) -> Quantity:
        """Quantity with dimensions (c, n, t, y), values from `config`."""
        # Extract MESSAGEix-Transport configuration
        cfg: "Config" = config["transport"]

        # Construct a set of all (node, technology, commodity) to constrain
        rows: List[List] = []
        cols = ["n", "t", "c", "value"]
        for (n, modes, c), value in cfg.minimum_activity.items():
            for m in (
                ["2W", "BUS", "LDV", "freight truck"] if modes == "ROAD" else ["RAIL"]
            ):
                m_idx = technologies.index(m)
                rows.extend([n, t, c, value] for t in techs_for(technologies[m_idx], c))

        # Assign y and value; convert to Quantity
        return Quantity(
            pd.DataFrame(rows, columns=cols)
            .assign(y=y0)
            .set_index(cols[:3] + ["y"])["value"],
            units="GWa",
        )

    k = KeySeq("bound_activity_lo:n-t-y:transport minimum")
    c.add(next(k), _, "n::ex world", "t::transport", "y0", "config")

    # Produce MESSAGE parameter bound_activity_lo:nl-t-ya-m-h
    kw = dict(
        dims=dict(node_loc="n", technology="t", year_act="y"),
        common=dict(mode="all", time="year"),
    )

    c.add(k["ixmp"], "as_message_df", k[0], name=k.name, **kw)
    return [k["ixmp"]]


def other(c: Computer, base: Key) -> List[Key]:
    """Generate MESSAGE parameter data for ``transport other *`` technologies."""
    from .key import gdp_index

    # Keys
    assert {"c", "n"} == set(base.dims)
    bcast = Key("broadcast:c-t:other transport")
    k_cnt = (base + "0") * "t"  # with added dimension "t"
    k_cnty = KeySeq(base * ("t", "y") + "1")  # with added dimensions "t", "y"

    def broadcast_other_transport(technologies) -> Quantity:
        """Transform e.g. c="gas" to (c="gas", t="transport other gas")."""
        rows = []
        cols = ["c", "t", "value"]

        for code in filter(lambda code: "other" in code.id, technologies):
            rows.append([code.eval_annotation(id="input")["commodity"], code.id, 1.0])

        return Quantity(pd.DataFrame(rows, columns=cols).set_index(cols[:-1])[cols[-1]])

    c.add(bcast, broadcast_other_transport, "t::transport")
    c.add(k_cnt, "mul", base, bcast)

    # Project values across y using GDP PPP index
    c.add(k_cnty[0], "mul", k_cnt, gdp_index)
    # Convert units to GWa
    c.add(k_cnty[1], "convert_units", k_cnty[0], quote("GWa"))

    # Produce MESSAGE parameter bound_activity_lo:nl-t-ya-m-h
    kw = dict(
        dims=dict(node_loc="n", technology="t", year_act="y"),
        common=dict(mode="all", time="year"),
    )
    k_bal = Key("bound_activity_lo::transport other+ixmp")
    c.add(k_bal, "as_message_df", k_cnty.prev, name=k_bal.name, **kw)

    # Divide by self to ensure values = 1.0 but same dimensionality
    c.add(k_cnty[2], "div", k_cnty[0], k_cnty[0])
    # Results in dimensionless; re-assign units
    c.add(k_cnty[3], "assign_units", k_cnty[2], quote("GWa"))

    # Produce MESSAGE parameter input:nl-t-yv-ya-m-no-c-l-h-ho
    kw["dims"].update(commodity="c", node_origin="n", year_vtg="y")
    kw["common"].update(level="final", time_origin="year")
    k_input = Key("input::transport other+ixmp")
    c.add(k_input, "as_message_df", k_cnty.prev, name=k_input.name, **kw)

    result = Key("transport other::ixmp")
    c.add(result, "merge_data", k_bal, k_input)
    return [result]


def usage_data(
    load_factor: Quantity, modes: List[Code], nodes: List[str], years: List[int]
) -> Mapping[str, pd.DataFrame]:
    """Generate data for non-LDV usage "virtual" technologies.

    These technologies convert commodities like "transport vehicle rail" (i.e.
    vehicle-distance traveled) into "transport pax rail" (i.e. passenger-distance
    traveled), through use of a load factor in the ``output`` efficiency.

    They are "virtual" in the sense they have no cost, lifetime, or other physical
    properties.
    """
    common = dict(year_vtg=years, year_act=years, mode="all", time="year")

    data = []
    for mode in filter(lambda m: m != "LDV", map(str, modes)):
        data.append(
            make_io(
                src=(f"transport vehicle {mode.lower()}", "useful", "Gv km"),
                dest=(f"transport pax {mode.lower()}", "useful", "Gp km"),
                efficiency=load_factor.sel(t=mode.upper()).item(),
                on="output",
                technology=f"transport {mode.lower()} usage",
                # Other data
                **common,
            )
        )

    result: Dict[str, pd.DataFrame] = dict()
    merge_data(result, *data)

    for k, v in result.items():
        result[k] = v.pipe(broadcast, node_loc=nodes).pipe(same_node).pipe(same_time)

    return result
