# eliteBonusCoverOpsScanProbeStrength2
#
# Used by:
# Ships from group: Covert Ops (5 of 5)
type = "passive"
def handler(fit, ship, context):
    fit.modules.filteredChargeBoost(lambda mod: mod.charge.group.name == "Scanner Probe",
                                    "baseSensorStrength", ship.getModifiedItemAttr("eliteBonusCoverOps2"), skill="Covert Ops")
