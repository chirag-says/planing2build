"""Benchmark corpus (research spike). Homeowner-style inputs in RQ v1 form plus provisional design
inputs. Plot sizes and setbacks are example inputs, not rules."""

BASE = {"plot_is_rectangular": True, "floors": "G", "basement": False, "built_up_area_sqft": "NOT_SURE"}
INPUTS = {"stair": "NONE"}


def case(w, d, facing, sb, bed, bath, *, pooja=False, car=True, vastu="NOT_NEEDED", attached=1,  # type: ignore[no-untyped-def]
         spaces=1, kind="CAR", dining="SEPARATE", kitchen="CLOSED", utility=False):  # fmt: skip
    answers = {**BASE, "plot_width_ft": w, "plot_depth_ft": d, "facing": facing,
               "setbacks": dict(zip(("FRONT", "BACK", "LEFT", "RIGHT"), sb, strict=True)),
               "bedrooms": str(bed), "bathrooms": str(bath), "pooja_room": pooja, "car_parking": car,
               "vastu": vastu}  # fmt: skip
    inputs = {**INPUTS, "attached_bathrooms": attached, "dining": dining, "kitchen": kitchen, "utility": utility}
    if car:
        inputs |= {"parking_spaces": spaces, "parking_kind": kind}
    return answers, inputs


CORPUS = {
    "2bhk_30x50_north_twowheeler_open": case(30, 50, "N", (5, 3, 2, 2), 2, 1, attached=0, kind="TWO_WHEELER",
                                             dining="IN_LIVING", kitchen="OPEN", utility=True),
    "3bhk_40x65_east_puja": case(40, 65, "E", (6, 4, 3, 3), 3, 2, pooja=True, vastu="WHERE_POSSIBLE"),
    "2bhk_40x80_west_two_cars": case(40, 80, "W", (5, 3, 3, 3), 2, 2, spaces=2, vastu="MUST_FOLLOW"),
    "1bhk_25x40_south_small": case(25, 40, "S", (4, 3, 2, 2), 1, 1, attached=0, kind="TWO_WHEELER"),
    "2bhk_22x60_narrow_deep": case(22, 60, "E", (5, 3, 2, 2), 2, 1, attached=0, kind="TWO_WHEELER"),
    "4bhk_50x80_large_two_cars": case(50, 80, "N", (8, 5, 4, 4), 4, 3, attached=2, spaces=2, pooja=True,
                                      utility=True, vastu="WHERE_POSSIBLE"),
    "3bhk_30x60_single_car_vastu": case(30, 60, "S", (5, 3, 2, 2), 3, 2, vastu="MUST_FOLLOW"),
    "2bhk_35x55_utility_no_vastu": case(35, 55, "W", (5, 3, 3, 3), 2, 2, utility=True),
    "3bhk_45x70_two_cars_puja": case(45, 70, "E", (6, 4, 3, 3), 3, 3, attached=2, spaces=2, pooja=True),
    "3bhk_40x60_asymmetric_setbacks": case(40, 60, "N", (10, 5, 5, 2), 3, 2, pooja=True),
    "2bhk_30x45_common_bath_only": case(30, 45, "E", (4, 3, 2, 2), 2, 1, attached=0),
    # expected infeasible
    "3bhk_20x30_too_small": case(20, 30, "S", (5, 3, 2, 2), 3, 2),
    "2bhk_30x60_two_cars_too_wide": case(30, 60, "E", (5, 3, 2, 2), 2, 2, spaces=2),
    "4bhk_30x40_overfull": case(30, 40, "N", (5, 3, 2, 2), 4, 3, attached=2),
}
