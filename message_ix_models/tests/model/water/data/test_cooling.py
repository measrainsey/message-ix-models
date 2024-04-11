import pytest
from message_ix import Scenario

from message_ix_models import ScenarioInfo

# from message_ix_models.model.structure import get_codes
from message_ix_models.model.water.data.water_for_ppl import cool_tech, non_cooling_tec


@pytest.mark.parametrize("RCP", ["no-climate", "6p0"])
def test_cool_tec(request, test_context, RCP):
    mp = test_context.get_platform()
    scenario_info = {
        "mp": mp,
        "model": f"{request.node.name}/test water model",
        "scenario": f"{request.node.name}/test water scenario",
        "version": "new",
    }
    s = Scenario(**scenario_info)
    s.add_horizon(year=[2020, 2030, 2040])
    s.add_set("technology", ["tech1", "tech2"])
    s.add_set("node", ["loc1", "loc2"])
    s.add_set("year", [2020, 2030, 2040])

    # TODO: this is where you would add
    #     "node_loc": ["loc1", "loc2"],
    #     "node_dest": ["dest1", "dest2"],
    #     "year_vtg": ["2020", "2020"],
    #     "year_act": ["2020", "2020"], etc
    # to the scenario as per usual. However, I don't know if that's necessary as the
    # test is passing without it, too.

    s.commit(comment="basic water non_cooling_tec test model")

    test_context.set_scenario(s)
    test_context["water build info"] = ScenarioInfo(scenario_obj=s)
    test_context.type_reg = "global"
    test_context.regions = "R11"
    test_context.time = "year"
    test_context.nexus_set = "nexus"
    # TODO add
    test_context.RCP = RCP

    # TODO: only leaving this in so you can see which data you might want to assert to
    # be in the result. Please remove after adapting the assertions below:
    # Mock the DataFrame read from CSV
    # df = pd.DataFrame(
    #     {
    #         "technology_group": ["cooling", "non-cooling"],
    #         "technology_name": ["cooling_tech1", "non_cooling_tech1"],
    #         "water_supply_type": ["freshwater_supply", "freshwater_supply"],
    #         "water_withdrawal_mid_m3_per_output": [1, 2],
    #     }
    # )

    result = cool_tech(context=test_context)

    # Assert the results
    assert isinstance(result, dict)
    assert "input" in result
    assert all(
        col in result["input"].columns
        for col in [
            "technology",
            "value",
            "unit",
            "level",
            "commodity",
            "mode",
            "time",
            "time_origin",
            "node_origin",
            "node_loc",
            "year_vtg",
            "year_act",
        ]
    )


def test_non_cooling_tec(request, test_context):
    mp = test_context.get_platform()
    scenario_info = {
        "mp": mp,
        "model": f"{request.node.name}/test water model",
        "scenario": f"{request.node.name}/test water scenario",
        "version": "new",
    }
    s = Scenario(**scenario_info)
    s.add_horizon(year=[2020, 2030, 2040])
    s.add_set("technology", ["tech1", "tech2"])
    s.add_set("node", ["loc1", "loc2"])
    s.add_set("year", [2020, 2030, 2040])

    # TODO: this is where you would add
    #     "node_loc": ["loc1", "loc2"],
    #     "node_dest": ["dest1", "dest2"],
    #     "year_vtg": ["2020", "2020"],
    #     "year_act": ["2020", "2020"], etc
    # to the scenario as per usual. However, I don't know if that's necessary as the
    # test is passing without it, too.

    s.commit(comment="basic water non_cooling_tec test model")

    # set_scenario() updates Context.scenario_info
    test_context.set_scenario(s)
    # print(test_context.get_scenario())

    # # TODO This is where and how you would add data to the context, but these are not
    # #required for non_cooling_tech()
    # test_context["water build info"] = ScenarioInfo(scenario_obj=s)
    # test_context.type_reg = "country"
    # test_context.regions = "test_region"
    # test_context.map_ISO_c = {"test_region": "test_ISO"}

    # TODO: only leaving this in so you can see which data you might want to assert to
    # be in the result. Please remove after adapting the assertions below:
    # Mock the DataFrame read from CSV
    # df = pd.DataFrame(
    #     {
    #         "technology_group": ["cooling", "non-cooling"],
    #         "technology_name": ["cooling_tech1", "non_cooling_tech1"],
    #         "water_supply_type": ["freshwater_supply", "freshwater_supply"],
    #         "water_withdrawal_mid_m3_per_output": [1, 2],
    #     }
    # )

    result = non_cooling_tec(context=test_context)

    # Assert the results
    assert isinstance(result, dict)
    assert "input" in result
    assert all(
        col in result["input"].columns
        for col in [
            "technology",
            "value",
            "unit",
            "level",
            "commodity",
            "mode",
            "time",
            "time_origin",
            "node_origin",
            "node_loc",
            "year_vtg",
            "year_act",
        ]
    )
