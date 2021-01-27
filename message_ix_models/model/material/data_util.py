from collections import defaultdict

import pandas as pd

from .util import read_config
import re

def modify_demand_and_hist_activity(scen):
    """Take care of demand changes due to the introduction of material parents

    Shed industrial energy demand properly.

    Also need take care of remove dynamic constraints for certain energy carriers.

    Adjust the historical activity of the related industry technologies

    that provide output to different categories of industrial demand (e.g.

    i_therm, i_spec, i_feed). The historical activity is reduced the same %

    as the industrial demand is reduced in modfiy_demand function.
    """

    # NOTE Temporarily modifying industrial energy demand
    # From IEA database (dumped to an excel)

    context = read_config()
    fname = "MESSAGEix-Materials_final_energy_industry.xlsx"
    df = pd.read_excel(context.get_path("material", fname),\
    sheet_name="Export Worksheet")

    # Filter the necessary variables
    df = df[(df["SECTOR"]== "feedstock (petrochemical industry)")|
        (df["SECTOR"]== "feedstock (total)") |  \
        (df["SECTOR"]== "industry (chemicals)") |
        (df["SECTOR"]== "industry (iron and steel)") | \
        (df["SECTOR"]== "industry (non-ferrous metals)") | \
        (df["SECTOR"]== "industry (non-metallic minerals)") | \
        (df["SECTOR"]== "industry (total)")]
    df = df[df["RYEAR"]==2015]

    # Retreive data for i_spec (Excludes petrochemicals as the share is negligable)
    # Aluminum, cement and steel included.
    # NOTE: Steel has high shares (previously it was not inlcuded in i_spec)

    df_spec = df[(df["FUEL"]=="electricity") & \
                 (df["SECTOR"] != "industry (total)") \
             & (df["SECTOR"]!= "feedstock (petrochemical industry)") \
             & (df["SECTOR"]!= "feedstock (total)")]
    df_spec_total = df[(df["SECTOR"]=="industry (total)") \
    & (df["FUEL"]=="electricity") ]

    df_spec_new = pd.DataFrame(columns=["REGION","SECTOR","FUEL","RYEAR",\
                                        "UNIT_OUT","RESULT"])
    for r in df_spec["REGION"].unique():
        df_spec_temp = df_spec[df_spec["REGION"]==r]
        df_spec_total_temp = df_spec_total[df_spec_total["REGION"] == r]
        df_spec_temp["i_spec"] = df_spec_temp["RESULT"]/df_spec_total_temp["RESULT"].values[0]
        df_spec_new = pd.concat([df_spec_temp,df_spec_new],ignore_index = True)

    df_spec_new.drop(["FUEL","RYEAR","UNIT_OUT","RESULT"],axis=1, inplace=True)
    df_spec_new.loc[df_spec_new["SECTOR"]=="industry (chemicals)","i_spec"] = \
    df_spec_new.loc[df_spec_new["SECTOR"]=="industry (chemicals)","i_spec"] * 0.7

    df_spec_new = df_spec_new.groupby(["REGION"]).sum().reset_index()

    # Retreive data for i_feed: Only for petrochemicals
    # It is assumed that the sectors that are explicitly covered in MESSAGE are
    # 50% of the total feedstock.

    df_feed = df[(df["SECTOR"]== "feedstock (petrochemical industry)") & \
             (df["FUEL"]== "total") ]
    df_feed_total = df[(df["SECTOR"]== "feedstock (total)") & (df["FUEL"]== "total")]
    df_feed_temp = pd.DataFrame(columns= ["REGION","i_feed"])
    df_feed_new = pd.DataFrame(columns= ["REGION","i_feed"])

    for r in df_feed["REGION"].unique():

        i = 0
        df_feed_temp.at[i,"REGION"] = r
        df_feed_temp.at[i,"i_feed"] = 0.7
        i = i + 1
        df_feed_new = pd.concat([df_feed_temp,df_feed_new],ignore_index = True)

    # df_feed = df[(df["SECTOR"]== "feedstock (petrochemical industry)") & \
    #          (df["FUEL"]== "total") ]
    # df_feed_total = df[(df["SECTOR"]== "feedstock (total)") \
    #                     & (df["FUEL"]== "total")]
    #
    # df_feed_new = pd.DataFrame(columns=["REGION","SECTOR","FUEL",\
    #                                     "RYEAR","UNIT_OUT","RESULT"])
    # for r in df_feed["REGION"].unique():
    #     df_feed_temp = df_feed[df_feed["REGION"]==r]
    #     df_feed_total_temp = df_feed_total[df_feed_total["REGION"] == r]
    #     df_feed_temp["i_feed"] = df_feed_temp["RESULT"]/df_feed_total_temp["RESULT"].values[0]
    #     df_feed_new = pd.concat([df_feed_temp,df_feed_new],ignore_index = True)
    #
    # df_feed_new.drop(["FUEL","RYEAR","UNIT_OUT","RESULT"],axis=1, inplace=True)
    # df_feed_new = df_feed_new.groupby(["REGION"]).sum().reset_index()

    # Retreive data for i_therm
    # NOTE: It is assumped that 50% of the chemicals category is HVCs
    # NOTE: Aluminum is excluded since refining process is not explicitly represented
    # NOTE: CPA has a 3% share while it used to be 30% previosuly ??

    df_therm = df[(df["FUEL"]!="electricity") & (df["FUEL"]!="total") \
                & (df["SECTOR"] != "industry (total)") \
                & (df["SECTOR"]!= "feedstock (petrochemical industry)") \
                & (df["SECTOR"]!= "feedstock (total)") \
                & (df["SECTOR"]!= "industry (non-ferrous metals)") ]
    df_therm_total = df[(df["SECTOR"]=="industry (total)") \
                      & (df["FUEL"]!="total") & (df["FUEL"]!="electricity")]
    df_therm_total = df_therm_total.groupby(by="REGION").\
                                    sum().drop(["RYEAR"],axis=1).reset_index()
    df_therm = df_therm.groupby(by=["REGION","SECTOR"]).\
                        sum().drop(["RYEAR"],axis=1).reset_index()
    df_therm_new = pd.DataFrame(columns=["REGION","SECTOR","FUEL",\
                                        "RYEAR","UNIT_OUT","RESULT"])

    for r in df_therm["REGION"].unique():
        df_therm_temp = df_therm[df_therm["REGION"]==r]
        df_therm_total_temp = df_therm_total[df_therm_total["REGION"] == r]
        df_therm_temp["i_therm"] = df_therm_temp["RESULT"]/df_therm_total_temp["RESULT"].values[0]
        df_therm_new = pd.concat([df_therm_temp,df_therm_new],\
                                                            ignore_index = True)
        df_therm_new = df_therm_new.drop(["RESULT"],axis=1)

    df_therm_new.drop(["FUEL","RYEAR","UNIT_OUT"],axis=1,inplace=True)
    df_therm_new.loc[df_therm_new["SECTOR"]=="industry (chemicals)","i_therm"] = \
    df_therm_new.loc[df_therm_new["SECTOR"]=="industry (chemicals)","i_therm"] * 0.7

    # Modify CPA based on https://www.iea.org/sankey/#?c=Japan&s=Final%20consumption.
    # Since the value did not allign with the one in the IEA website.
    index = ((df_therm_new["SECTOR"]=="industry (iron and steel)") \
    & (df_therm_new["REGION"]=="CPA"))
    df_therm_new.loc[index,"i_therm"] = 0.2

    df_therm_new = df_therm_new.groupby(["REGION"]).sum().reset_index()

    # TODO: Useful technology efficiencies will also be included

    # Add the modified demand and historical activity to the scenario

    # Relted technologies that have outputs to useful industry level.
    # Historical activity of theese will be adjusted
    tec_therm = ["biomass_i","coal_i","elec_i","eth_i","foil_i","gas_i",
                "h2_i","heat_i","hp_el_i", "hp_gas_i","loil_i",
                "meth_i","solar_i"]
    tec_fs = ["coal_fs","ethanol_fs","foil_fs","gas_fs","loil_fs","methanol_fs",]
    tec_sp = ["sp_coal_I","sp_el_I","sp_eth_I","sp_liq_I","sp_meth_I", "h2_fc_I"]

    thermal_df_hist = scen.par('historical_activity', filters={'technology':tec_therm})
    spec_df_hist = scen.par('historical_activity', filters={'technology':tec_sp})
    feed_df_hist = scen.par('historical_activity', filters={'technology':tec_fs})
    useful_thermal = scen.par('demand', filters={'commodity':'i_therm'})
    useful_spec = scen.par('demand', filters={'commodity':'i_spec'})
    useful_feed = scen.par('demand', filters={'commodity':'i_feed'})

    for r in df_therm_new["REGION"]:
        r_MESSAGE = "R11_" + r
        useful_thermal.loc[useful_thermal["node"]== r_MESSAGE ,"value"] = \
        useful_thermal.loc[useful_thermal["node"]== r_MESSAGE,"value"] * \
        (1 - df_therm_new.loc[df_therm_new["REGION"]==r,"i_therm"].values[0])

        thermal_df_hist.loc[thermal_df_hist["node_loc"]== r_MESSAGE ,"value"] = \
        thermal_df_hist.loc[thermal_df_hist["node_loc"]== r_MESSAGE,"value"] * \
        (1 - df_therm_new.loc[df_therm_new["REGION"]==r,"i_therm"].values[0])

    for r in df_spec_new["REGION"]:
        r_MESSAGE = "R11_" + r
        useful_spec.loc[useful_spec["node"]== r_MESSAGE ,"value"] = \
        useful_spec.loc[useful_spec["node"]== r_MESSAGE,"value"] * \
        (1 - df_spec_new.loc[df_spec_new["REGION"]==r,"i_spec"].values[0])

        spec_df_hist.loc[spec_df_hist["node_loc"]== r_MESSAGE ,"value"] = \
        spec_df_hist.loc[spec_df_hist["node_loc"]== r_MESSAGE,"value"] * \
        (1 - df_spec_new.loc[df_spec_new["REGION"]==r,"i_spec"].values[0])

    for r in df_feed_new["REGION"]:
        r_MESSAGE = "R11_" + r
        useful_feed.loc[useful_feed["node"]== r_MESSAGE ,"value"] = \
        useful_feed.loc[useful_feed["node"]== r_MESSAGE,"value"] * \
        (1 - df_feed_new.loc[df_feed_new["REGION"]==r,"i_feed"].values[0])

        feed_df_hist.loc[feed_df_hist["node_loc"]== r_MESSAGE ,"value"] = \
        feed_df_hist.loc[feed_df_hist["node_loc"]== r_MESSAGE,"value"] * \
        (1 - df_feed_new.loc[df_feed_new["REGION"]==r,"i_feed"].values[0])

    scen.check_out()
    scen.add_par("demand",useful_thermal)
    scen.add_par("demand",useful_spec)
    scen.add_par("demand",useful_feed)
    scen.commit("Demand values adjusted")

    scen.check_out()
    scen.add_par('historical_activity', thermal_df_hist)
    scen.add_par('historical_activity', spec_df_hist)
    scen.add_par('historical_activity', feed_df_hist)
    scen.commit(comment = 'historical activity for useful level industry \
    technologies adjusted')

    # For aluminum there is no significant deduction required
    # (refining process not included and thermal energy required from
    # recycling is not a significant share.)
    # For petro: based on 13.1 GJ/tonne of ethylene and the demand in the model

    # df = scen.par('demand', filters={'commodity':'i_therm'})
    # df.value = df.value * 0.38 #(30% steel, 25% cement, 7% petro)
    #
    # scen.check_out()
    # scen.add_par('demand', df)
    # scen.commit(comment = 'modify i_therm demand')

    # Adjust the i_spec.
    # Electricity usage seems negligable in the production of HVCs.
    # Aluminum: based on IAI China data 20%.

    # df = scen.par('demand', filters={'commodity':'i_spec'})
    # df.value = df.value * 0.80  #(20% aluminum)
    #
    # scen.check_out()
    # scen.add_par('demand', df)
    # scen.commit(comment = 'modify i_spec demand')

    # Adjust the i_feedstock.
    # 45 GJ/tonne of ethylene or propylene or BTX
    # 2020 demand of one of these: 35.7 Mt
    # Makes up around 30% of total feedstock demand.

    # df = scen.par('demand', filters={'commodity':'i_feed'})
    # df.value = df.value * 0.7  #(30% HVCs)
    #
    # scen.check_out()
    # scen.add_par('demand', df)
    # scen.commit(comment = 'modify i_feed demand')

    # NOTE Aggregate industrial coal demand need to adjust to
    #      the sudden intro of steel setor in the first model year

    t_i = ['coal_i','elec_i','gas_i','heat_i','loil_i','solar_i']

    for t in t_i:
        df = scen.par('growth_activity_lo', \
                filters={'technology':t, 'year_act':2020})

        scen.check_out()
        scen.remove_par('growth_activity_lo', df)
        scen.commit(comment = 'remove growth_lo constraints')

# Read in technology-specific parameters from input xlsx
# Now used for steel and cement, which are in one file
def read_sector_data(sectname):

    import numpy as np

    # Ensure config is loaded, get the context
    context = read_config()

    # data_df = data_steel_china.append(data_cement_china, ignore_index=True)
    data_df = pd.read_excel(
        context.get_path("material", context.datafile),
        sheet_name=sectname,
    )

    # Clean the data
    data_df = data_df \
        [['Region', 'Technology', 'Parameter', 'Level',  \
        'Commodity', 'Mode', 'Species', 'Units', 'Value']] \
        .replace(np.nan, '', regex=True)

    # Combine columns and remove ''
    list_series = data_df[['Parameter', 'Commodity', 'Level', 'Mode']] \
        .apply(list, axis=1).apply(lambda x: list(filter(lambda a: a != '', x)))
    list_ef = data_df[['Parameter', 'Species', 'Mode']] \
        .apply(list, axis=1)

    data_df['parameter'] = list_series.str.join('|')
    data_df.loc[data_df['Parameter'] == "emission_factor", \
        'parameter'] = list_ef.str.join('|')

    data_df = data_df.drop(['Parameter', 'Level', 'Commodity', 'Mode'] \
        , axis = 1)
    data_df = data_df.drop( \
        data_df[data_df.Value==''].index)

    data_df.columns = data_df.columns.str.lower()

    # Unit conversion

    # At the moment this is done in the excel file, can be also done here
    # To make sure we use the same units

    return data_df


# Read in time-dependent parameters
# Now only used to add fuel cost for bare model
def read_timeseries(filename):

    import numpy as np

    # Ensure config is loaded, get the context
    context = read_config()

    if context.scenario_info['scenario'] == 'NPi400':
        sheet_name="timeseries_NPi400"
    else:
        sheet_name = "timeseries"

    # Read the file
    df = pd.read_excel(
        context.get_path("material", filename), sheet_name)

    import numbers
    # Take only existing years in the data
    datayears = [x for x in list(df) if isinstance(x, numbers.Number)]

    df = pd.melt(df, id_vars=['parameter', 'region', 'technology', 'mode', 'units'], \
        value_vars = datayears, \
        var_name ='year')

    df = df.drop(df[np.isnan(df.value)].index)
    return df


def read_rel(filename):

    import numpy as np

    # Ensure config is loaded, get the context
    context = read_config()

    # Read the file
    data_rel = pd.read_excel(
        context.get_path("material", filename), sheet_name="relations",
    )

    return data_rel
